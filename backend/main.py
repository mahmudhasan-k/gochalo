"""Anonymous, bounded API. Content lives only in process memory."""
import asyncio
import hashlib
import json
import os
import secrets
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

sys.path.insert(0, str(Path(__file__).parent / "engine"))
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse,StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
import ai_service
import research
from result_metadata import metadata
import url_input
from examples import load_example
from official_examples import load_official_example
from image_input import prepare_image
from ocr_service import extract_image_text
from job_progress import callback as progress_callback
from result_contract import finalize
from gemini_requests import attempt_log, job_deadline
from evaluation_trace import sink as trace_sink, record as record_trace
from session_admission import SessionAdmission

TTL = 1800
MAX_RETAINED_JOBS = 200
jobs = {}
sessions = {}
tasks = set()
slots = None
session_admission = SessionAdmission()

class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    request_id: str = Field(default="", max_length=80)

class LinkBody(StrictBody):
    url: str = Field(min_length=1, max_length=4096)
    revision: str = Field(min_length=1, max_length=80)

class AnalysisBody(StrictBody):
    text: str = Field(default="", max_length=50000)
    extraction_job_id: str = Field(default="", max_length=80)
    language: Literal["bn", "en"] = "bn"
    kind: Literal["link", "image", "text", "ask"]
    reviewed: bool = False
    revision: str = Field(min_length=1, max_length=80)

class ResearchBody(StrictBody):
    query: str = Field(min_length=1, max_length=2000)
    context: str = Field(default="", max_length=500)
    language: Literal["bn", "en"] = "bn"
    revision: str = Field(min_length=1, max_length=80)

def cleanup():
    now = time.monotonic()
    for key in list(jobs):
        if now - jobs[key]["created"] > TTL and jobs[key]["status"] not in ("queued", "running"):
            del jobs[key]
    for key in list(sessions):
        if now - sessions[key]["touched"] > TTL and not sessions[key]["active"]:
            del sessions[key]

def session(token):
    cleanup()
    if not token or token not in sessions:
        raise HTTPException(401, "session_expired")
    state = sessions[token]
    state["touched"] = time.monotonic()
    return state

def distinct_fee_claims(claims, evidence):
    """Display complete source statements once; never infer identity from citations alone."""
    quotes = {item.id: " ".join(item.excerpt.split()) for item in evidence if item.excerpt_found}
    displayed, positions = [], {}
    for claim in claims:
        signature = None
        text = " ".join(claim.text.split())
        if claim.evidence_status == "quotation_matched" and claim.semantic_status == "supported":
            refs = frozenset(claim.evidence_ids)
            for ref in sorted(refs):
                quote = quotes.get(ref)
                # Both complete statements stay verbatim. Only the observed
                # sentence boundary vs additive conjunction may differ.
                if quote and text in (quote, quote.replace("। ", " এবং ")):
                    signature = (refs, quote)
                    break
        if signature is not None and signature in positions:
            if text == signature[1]:
                displayed[positions[signature]] = claim  # Prefer the existing literal formulation.
            continue
        if signature is not None:
            positions[signature] = len(displayed)
        displayed.append(claim)
    return displayed

def public_result(result, *, demo=False):
    output=finalize(_admitted_result(result, demo=demo))
    record_trace("public_admission", output=output)
    return output


def _admitted_result(result, *, demo=False):
    """Never serialize withheld generated wording or unreviewed dynamic claims."""
    if isinstance(result, ai_service.GeneralAskResult):
        sections = {name:[{"text":text, "evidence_ids":[]} for text in getattr(result,name)]
                    for name in ("explanation", "steps", "documents", "fees", "deadlines")}
        return {"sections":sections,
                "section_states":{name:"available" if items else "unconfirmed" for name,items in sections.items()},
                "evidence":[], "unknowns":[{"kind":item.kind, "category":item.category,
                    "reason_code":"incomplete_review", "text":item.text, "evidence_ids":[]} for item in result.unknowns],
                "withheld_count":0, "partial":False, "demo":False,
                "has_guidance":bool(result.steps or result.documents), "review_mode":"general_ask",
                "semantic_review_complete":False}
    deterministic=(result.review_mode=="deterministic_only" and bool(result.review_failure))
    if not demo and not result.semantic_review_complete and not deterministic:
        raise ai_service.AnalysisError("review_failed", "Review incomplete")
    held = 0
    matched_ids = {item.id for item in result.evidence if item.excerpt_found}
    def eligible(items):
        nonlocal held
        output=[]
        for item in items:
            if item.evidence_status == "quotation_matched" and item.evidence_ids and set(item.evidence_ids) <= matched_ids and (demo or item.semantic_status == "supported" or deterministic and item.semantic_status=="not_reviewed"):
                conditions_supported=all(any(ai_service._quotation_key(condition) in ai_service._quotation_key(e.excerpt)
                    for e in result.evidence if e.excerpt_found and e.id in item.evidence_ids) for condition in item.source_conditions)
                if not conditions_supported:
                    held+=1
                    continue
                output.append({"text":item.text, "evidence_ids":item.evidence_ids,
                    **({"source_conditions":item.source_conditions} if item.source_conditions else {})})
            else:
                held += 1
        return output
    sections = {name:eligible(getattr(result,name)) for name in ("explanation","steps","documents")}
    sections["fees"]=eligible(distinct_fee_claims(result.fees_and_deadlines.fees,result.evidence))
    sections["deadlines"]=eligible(result.fees_and_deadlines.deadlines)
    evidence=[{"id":e.id,"excerpt":e.excerpt} for e in result.evidence if e.excerpt_found]
    ids={e["id"] for e in evidence}
    raw_sections = {name:getattr(result,name) for name in ("explanation","steps","documents")}
    raw_sections.update(fees=result.fees_and_deadlines.fees, deadlines=result.fees_and_deadlines.deadlines)
    language = getattr(result,"output_language","bn")
    unknowns, section_states = metadata(result, sections, ids, raw_sections, demo=demo, language=language)
    return {"sections":sections, "section_states":section_states, "evidence":evidence, "unknowns":unknowns,
            "withheld_count":held, "partial":bool(held), "demo":demo,
            "has_guidance":any(sections.values()),"review_mode":"saved_example" if demo else result.review_mode,
            "semantic_review_complete":False if demo else result.semantic_review_complete}

async def execute(job_id, state, work):
    job=jobs[job_id]
    try:
        async with slots:
            job["status"]="running"
            job["stage"]=job["operation"]
            marker=progress_callback.set(lambda stage:job.update(stage=stage))
            ledger=attempt_log.set(job["attempts"])
            deadline=job_deadline.set(time.monotonic()+600)
            trace=trace_sink.set(job["trace"] if os.environ.get("LOCAL_EVALUATION_CAPTURE")=="true"
                and os.environ.get("APP_ENV","development").lower() not in {"production","prod"} else None)
            try:
                result=await work()
                if time.monotonic() >= job_deadline.get():
                    raise ai_service.AnalysisError("job_timeout", "Operation reached its time limit.")
                job["result"]=result
            finally:
                job_deadline.reset(deadline)
                attempt_log.reset(ledger)
                trace_sink.reset(trace)
                progress_callback.reset(marker)
            job["status"]="succeeded"
            job["stage"]="done"
    except (ai_service.AnalysisError,url_input.ExtractionError) as error:
        job["status"]="failed"
        job["error"]=error.code
        diagnostics=getattr(error,"diagnostics",None)
        if diagnostics is not None:
            # ProviderDiagnostics is a fixed allowlist; raw provider errors
            # and request credentials are never retained on the owned job.
            job["provider_diagnostics"]=diagnostics.model_dump()
    except Exception:
        job["status"]="failed"
        job["error"]="unexpected"
    finally:
        state["active"]=None

def enqueue(token, revision, operation, work, fingerprint=None, request_id="", *, source_kind=None):
    state=session(token)
    if request_id:
        for job_id, previous in jobs.items():
            if previous["owner"]==token and previous.get("request_id")==request_id:
                if (previous["revision"],previous["operation"],previous.get("fingerprint"))!=(revision,operation,fingerprint):
                    raise HTTPException(409,"request_id_conflict")
                return {"job_id":job_id}
    if state["active"]:
        previous=jobs.get(state["active"])
        if fingerprint and previous and previous.get("fingerprint")==fingerprint:
            return {"job_id":state["active"]}
        raise HTTPException(409,"operation_in_progress")
    active=sum(j["status"] in ("queued","running") for j in jobs.values())
    if active>=3:
        raise HTTPException(429,"queue_full")
    # TTL alone does not bound completed/failed jobs during a busy half hour.
    # Keep existing results available; reject new work rather than evicting them.
    if len(jobs)>=MAX_RETAINED_JOBS:
        raise HTTPException(503,"job_capacity")
    job_id=secrets.token_urlsafe(24)
    jobs[job_id]={"owner":token,"created":time.monotonic(),"revision":revision,
        "operation":operation,"status":"queued","stage":"queued","result":None,"error":None,
        "fingerprint":fingerprint,"request_id":request_id,"attempts":[],"trace":[],"source_kind":source_kind}
    state["active"]=job_id
    task=asyncio.create_task(execute(job_id,state,work))
    tasks.add(task)
    task.add_done_callback(tasks.discard)
    return {"job_id":job_id}

@asynccontextmanager
async def lifespan(app):
    global slots
    slots=asyncio.Semaphore(1)
    yield
    for task in list(tasks):
        task.cancel()
    await asyncio.gather(*tasks,return_exceptions=True)
    tasks.clear()
    jobs.clear()
    sessions.clear()
    session_admission.clear()

class BoundedBody:
    """Bound request bytes before JSON parsing and reject stalled uploads."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in ("POST", "PUT", "PATCH"):
            return await self.app(scope, receive, send)
        limit = 5 * 1024 * 1024 if scope["path"] == "/api/extract/image" else 128 * 1024
        headers = dict(scope.get("headers", []))
        try:
            length = int(headers.get(b"content-length", b"0"))
            if length < 0:
                raise ValueError
        except ValueError:
            response = JSONResponse(status_code=400, content={"detail": "invalid_input"})
            return await response(scope, receive, send)
        if length > limit:
            response = JSONResponse(status_code=413, content={"detail": "request_too_large"})
            return await response(scope, receive, send)
        body = bytearray()
        try:
            async with asyncio.timeout(20):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    body.extend(message.get("body", b""))
                    if len(body) > limit:
                        response = JSONResponse(status_code=413, content={"detail": "request_too_large"})
                        return await response(scope, receive, send)
                    if not message.get("more_body", False):
                        break
        except TimeoutError:
            response = JSONResponse(status_code=408, content={"detail": "upload_timeout"})
            return await response(scope, receive, send)
        delivered = False
        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()
        await self.app(scope, bounded_receive, send)

class ApiPrivacyHeaders:
    """Guest-specific API responses must not be stored in browser/shared caches."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        async def privacy_send(message):
            if scope["type"] == "http" and scope["path"].startswith("/api/") and message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend([(b"cache-control", b"no-store, private"), (b"pragma", b"no-cache"),
                                (b"x-content-type-options", b"nosniff")])
                message = {**message, "headers": headers}
            await send(message)
        await self.app(scope, receive, privacy_send)

app=FastAPI(title="Gochalo API",lifespan=lifespan)
app.add_middleware(BoundedBody)
app.add_middleware(CORSMiddleware,
    allow_origins=[value.strip().rstrip("/") for value in os.environ.get("FRONTEND_ORIGINS","http://localhost:5173,http://127.0.0.1:5173").split(",") if value.strip()],
    allow_methods=["GET","POST"], allow_headers=["Content-Type","X-Session-Token"])

app.add_middleware(ApiPrivacyHeaders)

@app.exception_handler(RequestValidationError)
async def validation_error(request, error):
    # FastAPI's default response echoes invalid input, potentially including source text.
    return JSONResponse(status_code=422,content={"detail":"invalid_input"})

@app.get("/api/health")
async def health():
    return {"status":"ok","analysis_enabled":ai_service.analysis_enabled(),"research_enabled":research.enabled()}

@app.post("/api/session")
async def new_session(request: Request):
    cleanup()
    if len(sessions)>=1000:
        raise HTTPException(503,"session_capacity")
    # Uvicorn may normalize a trusted proxy's client address. Never parse
    # X-Forwarded-For here: an arbitrary caller must not reset admission.
    retry = session_admission.reserve(request.client.host if request.client else "unknown")
    if retry:
        raise HTTPException(429,"rate_limit",headers={"Retry-After":str(retry)})
    token=secrets.token_urlsafe(32)
    sessions[token]={"touched":time.monotonic(),"active":None}
    return {"token":token}

@app.get("/api/example")
def example(language:Literal["bn","en"]="bn",audience:Literal["general","student"]="general",catalogue:Literal["fictional","epassport"]="fictional"):
    value=load_official_example(output_language=language) if catalogue=="epassport" else load_example(output_language=language,audience=audience)
    if value is None:
        raise HTTPException(503,"example_unavailable")
    source,result=value
    return {"source":source.source_text,"saved_on":source.saved_on,
        "source_url":getattr(source,"source_url",None),"fictional":catalogue=="fictional",
        "title":source.title_bn if language=="bn" else getattr(source,"title_en","E-passport: saved official-source excerpt"),
        "result":public_result(result,demo=True)}

@app.post("/api/extract/link",status_code=202)
async def link(body:LinkBody,x_session_token:str=Header(default="")):
    # Syntactic admission before queueing; DNS admission remains in the extractor.
    try:
        url_input.normalize_url(body.url)
    except url_input.ExtractionError as error:
        raise HTTPException(400,error.code) from None
    async def work():
        record_trace("link_extraction",event="input",url=body.url)
        result=await url_input.extract_url(body.url,session=url_input.ExtractionSession())
        record_trace("link_extraction",event="cleaned_source",text=result.text,requested_url=result.requested_url,returned_url=result.returned_url)
        return {"text":result.text,"requested_url":result.requested_url,
            "returned_url":result.returned_url,"retrieved_at":result.retrieved_at.isoformat(),"title":result.title}
    fingerprint=hashlib.sha256(body.model_dump_json().encode()).hexdigest()
    return enqueue(x_session_token,body.revision,"extracting",work,fingerprint,body.request_id,source_kind="link")

@app.post("/api/extract/image",status_code=202)
async def image(request:Request,revision:str,request_id:str="",x_session_token:str=Header(default="")):
    session(x_session_token)
    if not revision or len(revision)>80:
        raise HTTPException(422,"invalid_revision")
    if len(request_id)>80:
        raise HTTPException(422,"invalid_request_id")
    mime=request.headers.get("content-type","").split(";")[0]
    if mime not in ("image/png","image/jpeg"):
        raise HTTPException(400,"image_invalid")
    filename="notice.png" if mime=="image/png" else "notice.jpg"
    buffer=bytearray()
    async for chunk in request.stream():
        if len(buffer)+len(chunk)>5*1024*1024:
            raise HTTPException(413,"image_size")
        buffer.extend(chunk)
    data=bytes(buffer)
    try:
        prepare_image(data,filename)
    except ai_service.AnalysisError as error:
        raise HTTPException(400,error.code) from None
    async def work():
        text=await asyncio.to_thread(extract_image_text,data,filename)
        return {"text":text}
    fingerprint=hashlib.sha256(mime.encode()+b"\0"+data).hexdigest()
    return enqueue(x_session_token,revision,"extracting",work,fingerprint,request_id,source_kind="image")

@app.post("/api/analysis",status_code=202)
async def analyze(body:AnalysisBody,x_session_token:str=Header(default="")):
    session(x_session_token)
    text=body.text
    if body.extraction_job_id:
        extracted=jobs.get(body.extraction_job_id)
        if (body.text or body.kind not in ("link","image") or not extracted
                or extracted["owner"]!=x_session_token or extracted["status"]!="succeeded"
                or extracted["operation"]!="extracting"
                or extracted.get("source_kind")!=body.kind):
            raise HTTPException(422,"invalid_source_reference")
        text=extracted["result"].get("text","")
    if not text.strip() or len(text)>50000:
        raise HTTPException(422,"invalid_input")
    if body.kind == "ask" and len(body.text) > 2000:
        raise HTTPException(422,"invalid_input")
    if not ai_service.analysis_enabled():
        raise HTTPException(503,"analysis_paused")
    async def work():
        analyzer=ai_service.analyze_ask if body.kind == "ask" else ai_service.analyze_instructions
        result=await asyncio.to_thread(analyzer,text,output_language=body.language)
        return {**public_result(result), "source_reviewed": body.reviewed}
    fingerprint=hashlib.sha256(body.model_dump_json().encode()).hexdigest()
    return enqueue(x_session_token,body.revision,"analyzing",work,fingerprint,body.request_id)

@app.post("/api/research",status_code=202)
async def research_plan(body:ResearchBody,x_session_token:str=Header(default="")):
    session(x_session_token)
    if not body.query.strip():
        raise HTTPException(422,"invalid_input")
    if not research.enabled():
        raise HTTPException(503,"research_unavailable")
    async def work():
        return await asyncio.to_thread(research.analyze_research,body.query,
                                      output_language=body.language,context=body.context)
    fingerprint=hashlib.sha256(body.model_dump_json().encode()).hexdigest()
    return enqueue(x_session_token,body.revision,"researching",work,fingerprint,body.request_id)

@app.get("/api/requests/{request_id}")
async def find_request(request_id:str,x_session_token:str=Header(default="")):
    session(x_session_token)
    if not request_id or len(request_id)>80:
        raise HTTPException(422,"invalid_request_id")
    for job_id,job in jobs.items():
        if job["owner"]==x_session_token and job.get("request_id")==request_id:
            return {"job_id":job_id}
    raise HTTPException(404,"job_not_found")

@app.get("/api/jobs/{job_id}")
async def status(job_id:str,x_session_token:str=Header(default="")):
    session(x_session_token)
    job=jobs.get(job_id)
    if not job or job["owner"]!=x_session_token:
        raise HTTPException(404,"job_not_found")
    return {key:job[key] for key in ("revision","operation","status","stage","result","error")}


@app.get("/api/jobs/{job_id}/diagnostics")
async def diagnostics(job_id:str,x_session_token:str=Header(default="")):
    await status(job_id,x_session_token)
    result={"attempts":list(jobs[job_id]["attempts"])}
    if jobs[job_id].get("provider_diagnostics"):
        result["provider_diagnostics"]=dict(jobs[job_id]["provider_diagnostics"])
    if jobs[job_id]["trace"]:
        result["trace"]=list(jobs[job_id]["trace"])
    return result

@app.get("/api/jobs/{job_id}/stream")
async def stream_job(job_id:str,request:Request,x_session_token:str=Header(default="")):
    # Admission happens before headers so failures remain normal JSON HTTP errors.
    await status(job_id,x_session_token)
    async def events():
        previous=None
        last_ping=time.monotonic()
        deadline=last_ping+600
        while time.monotonic()<deadline and not await request.is_disconnected():
            try:
                snapshot=await status(job_id,x_session_token)
            except HTTPException:
                return
            signature=(snapshot["status"],snapshot["stage"])
            if signature!=previous:
                event={**snapshot,"stage":"completed" if snapshot["status"]=="succeeded" else "failed" if snapshot["status"]=="failed" else snapshot["stage"]}
                yield "event: job\ndata: "+json.dumps(event,ensure_ascii=False)+"\n\n"
                previous=signature
            if snapshot["status"] in {"succeeded","failed"}:
                return
            if time.monotonic()-last_ping>=15:
                yield ": keepalive\n\n"
                last_ping=time.monotonic()
            await asyncio.sleep(.25)
    return StreamingResponse(events(),media_type="text/event-stream",headers={"Cache-Control":"no-store, private","X-Accel-Buffering":"no"})


# Same-origin deployment: API routes above retain precedence.
static_root = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if static_root.is_dir():
    from fastapi.staticfiles import StaticFiles
    from starlette.middleware.gzip import GZipMiddleware

    class FrontendFiles(StaticFiles):
        async def get_response(self, path, scope):
            response = await super().get_response(path, scope)
            response.headers["Cache-Control"] = ("public, max-age=31536000, immutable"
                if path.replace("\\", "/").lstrip("/").startswith("assets/") else "no-cache")
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            return response

    # Compress public assets only; API data and progress streams bypass gzip.
    app.mount("/", GZipMiddleware(FrontendFiles(directory=str(static_root), html=True),
        minimum_size=1024, compresslevel=5), name="frontend")
