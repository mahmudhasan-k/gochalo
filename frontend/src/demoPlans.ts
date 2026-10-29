import {createRetrieval,type Lang,type PlanResult} from './productTypes';
const demos={
 "en": [
  {
   "title": "How do I fix spelling of my name on NID?",
   "category": "Identity",
   "overview": "A spelling correction is different from a legal name change. Start by comparing your NID record with your supporting records, then confirm the applicable process with Bangladesh Election Commission services.",
   "steps": [
    "Compare the spelling across your NID and supporting records; note exactly what needs correcting.",
    "Check the official NID services portal or election office for the correction category and accepted evidence.",
    "Prepare the relevant files, complete the correction request, and review every field before submitting.",
    "If a fee is shown, confirm the amount and payment instructions before paying.",
    "Keep the acknowledgement and track the request; respond if further evidence is requested."
   ],
   "prep": [
    "Current NID record",
    "Supporting record showing the intended spelling, subject to official acceptance",
    "Application acknowledgement, after submission"
   ],
   "fees": [
    "Any correction charge depends on the applicable category; confirm the amount through official services."
   ],
   "deadlines": [
    "No guaranteed correction time is provided in this demo. Check your application status and any request-specific response deadline."
   ]
  },
  {
   "title": "How do I apply to Harvard University from Bangladesh?",
   "category": "Education",
   "overview": "For an undergraduate applicant in Bangladesh. Graduate and professional programs have separate processes. Admission and financial aid decisions depend on the relevant application and review.",
   "steps": [
    "Choose undergraduate study or a specific graduate program before following an application checklist.",
    "Read the selected program’s official application instructions for your entry year.",
    "Plan your academic records, essays and recommendations; check translation and testing rules for your situation.",
    "Complete the application through the route listed by the university and review all entries.",
    "If seeking financial aid, follow the applicable international applicant instructions and separate deadlines.",
    "Submit by the relevant deadline, retain confirmation and monitor requests for updates."
   ],
   "prep": [
    "Academic records and translations, where required",
    "Application essays or personal statements",
    "Recommendations, where required",
    "Test results, if required for the chosen program and cycle",
    "Financial-aid records, if applying for aid"
   ],
   "fees": [
    "Check the application charge and any available fee-waiver process for the chosen program. Financial aid is a separate assessment."
   ],
   "deadlines": [
    "Application and financial-aid deadlines vary by program, entry year and application round; verify each on official Harvard pages."
   ]
  },
  {
   "title": "E-passport renewal procedures",
   "category": "Travel",
   "overview": "Bangladesh e-passport reissue or renewal. Your route may differ for expiry, loss, damage, changed information, or an application made abroad. Confirm the requirements for your own case.",
   "steps": [
    "Identify the reason for reissue and whether you will apply in Bangladesh or through a mission abroad.",
    "Check the official e-passport or relevant mission instructions for your case.",
    "Prepare the applicable records and complete the online application, checking identity details carefully.",
    "Confirm the available passport option, fee and payment route before paying.",
    "Follow the applicable appointment and in-person submission instructions; bring the required records.",
    "Keep the delivery slip, track progress and follow the collection instructions."
   ],
   "prep": [
    "Existing passport, if available and applicable",
    "Identity records accepted for your case",
    "Application summary and appointment confirmation, if issued",
    "Payment receipt, if applicable",
    "Additional records for loss, damage or changed details, when required"
   ],
   "fees": [
    "The charge depends on passport options, service and application location. Confirm the current official amount; this demo does not quote a fee."
   ],
   "deadlines": [
    "Processing and appointment timing depend on the service and application location. Confirm locally rather than treating a processing estimate as a guarantee."
   ]
  }
 ],
 "bn": [
  {
   "title": "এনআইডিতে নামের বানান কীভাবে ঠিক করব?",
   "category": "Identity",
   "overview": "নামের বানান সংশোধনের প্রক্রিয়া ও গ্রহণযোগ্য কাগজপত্র সরকারি সেবায় মিলিয়ে নিন।",
   "steps": [
    "এনআইডি ও সমর্থক নথির বানান মিলিয়ে সংশোধনের অংশ লিখে রাখুন।",
    "সরকারি এনআইডি সেবা বা নির্বাচন অফিসে সংশোধনের ধরন ও গ্রহণযোগ্য প্রমাণ মিলিয়ে নিন।",
    "প্রযোজ্য নথি প্রস্তুত করে আবেদন পূরণ করুন এবং জমা দেওয়ার আগে সব তথ্য পড়ুন।",
    "ফি দেখালে পরিমাণ ও পরিশোধের নির্দেশনা মিলিয়ে নিন।",
    "আবেদনের প্রাপ্তিস্বীকার রাখুন, অবস্থা দেখুন এবং বাড়তি প্রমাণ চাইলে উত্তর দিন।"
   ],
   "prep": [
    "বর্তমান এনআইডির তথ্য",
    "সঠিক বানানের সমর্থক নথি, সরকারি গ্রহণযোগ্যতা অনুযায়ী",
    "জমার পরে পাওয়া প্রাপ্তিস্বীকার"
   ],
   "fees": [
    "প্রযোজ্য ফি সরকারি সেবায় মিলিয়ে নিন। এই ডেমোতে বর্তমান পরিমাণ নিশ্চিত করা হয়নি।"
   ],
   "deadlines": [
    "নিজের আবেদন ও প্রযোজ্য প্রক্রিয়ার সময় সরকারি নির্দেশনায় মিলিয়ে নিন। এই ডেমো কোনো নির্দিষ্ট সময়ের নিশ্চয়তা দেয় না।"
   ]
  },
  {
   "title": "বাংলাদেশ থেকে হার্ভার্ড বিশ্ববিদ্যালয়ে কীভাবে আবেদন করব?",
   "category": "Education",
   "overview": "স্নাতক ও স্নাতকোত্তর প্রোগ্রামের আবেদন আলাদা; নির্বাচিত প্রোগ্রামের বর্তমান নির্দেশনা মিলিয়ে নিন।",
   "steps": [
    "স্নাতক নাকি নির্দিষ্ট স্নাতকোত্তর প্রোগ্রামে আবেদন করবেন, ঠিক করুন।",
    "নির্বাচিত শিক্ষাবর্ষ ও প্রোগ্রামের সরকারি আবেদন নির্দেশনা পড়ুন।",
    "শিক্ষাগত নথি, রচনা ও সুপারিশ প্রস্তুতির পরিকল্পনা করুন; অনুবাদ ও পরীক্ষার শর্ত মিলিয়ে নিন।",
    "বিশ্ববিদ্যালয়ের নির্দেশিত পথে আবেদন পূরণ করে তথ্য মিলিয়ে নিন।",
    "আর্থিক সহায়তা চাইলে আন্তর্জাতিক আবেদনকারীদের আলাদা শর্ত ও সময়সীমা দেখুন।",
    "প্রযোজ্য সময়ের মধ্যে জমা দিয়ে নিশ্চিতকরণ রাখুন এবং পরবর্তী বার্তা দেখুন।"
   ],
   "prep": [
    "শিক্ষাগত নথি ও প্রযোজ্য অনুবাদ",
    "আবেদনের রচনা বা ব্যক্তিগত বিবৃতি",
    "প্রযোজ্য সুপারিশপত্র",
    "প্রোগ্রাম ও শিক্ষাবর্ষ অনুযায়ী প্রয়োজন হলে পরীক্ষার ফল",
    "আর্থিক সহায়তা চাইলে প্রযোজ্য নথি"
   ],
   "fees": [
    "প্রযোজ্য ফি সরকারি সেবায় মিলিয়ে নিন। এই ডেমোতে বর্তমান পরিমাণ নিশ্চিত করা হয়নি।"
   ],
   "deadlines": [
    "নিজের আবেদন ও প্রযোজ্য প্রক্রিয়ার সময় সরকারি নির্দেশনায় মিলিয়ে নিন। এই ডেমো কোনো নির্দিষ্ট সময়ের নিশ্চয়তা দেয় না।"
   ]
  },
  {
   "title": "ই-পাসপোর্ট নবায়নের নিয়ম",
   "category": "Travel",
   "overview": "আবেদনের কারণ ও অবস্থান অনুযায়ী শর্ত আলাদা হতে পারে; সরকারি নির্দেশনা মিলিয়ে নিন।",
   "steps": [
    "পুনঃইস্যুর কারণ ও দেশ বা বিদেশ থেকে আবেদনের পথ ঠিক করুন।",
    "নিজের ক্ষেত্রে প্রযোজ্য সরকারি ই-পাসপোর্ট বা মিশনের নির্দেশনা পড়ুন।",
    "প্রযোজ্য নথি প্রস্তুত করে অনলাইন আবেদন পূরণ করুন; পরিচয়ের তথ্য ভালো করে মিলিয়ে নিন।",
    "পরিশোধের আগে পাসপোর্টের ধরন, ফি ও পরিশোধের পথ মিলিয়ে নিন।",
    "প্রযোজ্য সাক্ষাৎ ও সশরীরে জমার নির্দেশনা অনুসরণ করুন; প্রয়োজনীয় নথি সঙ্গে নিন।",
    "ডেলিভারি স্লিপ রাখুন, অগ্রগতি দেখুন এবং সংগ্রহের নির্দেশনা অনুসরণ করুন।"
   ],
   "prep": [
    "প্রযোজ্য ও পাওয়া গেলে বর্তমান পাসপোর্ট",
    "নিজের ক্ষেত্রে গ্রহণযোগ্য পরিচয়ের নথি",
    "ইস্যু হলে আবেদনের সারাংশ ও সাক্ষাতের নিশ্চিতকরণ",
    "প্রযোজ্য ফি পরিশোধের রসিদ",
    "হারানো, ক্ষতি বা তথ্য বদলের ক্ষেত্রে প্রয়োজন হলে বাড়তি নথি"
   ],
   "fees": [
    "প্রযোজ্য ফি সরকারি সেবায় মিলিয়ে নিন। এই ডেমোতে বর্তমান পরিমাণ নিশ্চিত করা হয়নি।"
   ],
   "deadlines": [
    "নিজের আবেদন ও প্রযোজ্য প্রক্রিয়ার সময় সরকারি নির্দেশনায় মিলিয়ে নিন। এই ডেমো কোনো নির্দিষ্ট সময়ের নিশ্চয়তা দেয় না।"
   ]
  }
 ]
};
export function demoCatalogue(lang:Lang){return demos[lang]}
export function openDemo(lang:Lang,index:number){
 const demo=demos[lang][index];const claim=(text:string)=>({text,evidence_ids:[]});
 const result:PlanResult={review_mode:'saved_example',demo:true,semantic_review_complete:false,sections:{explanation:[claim(demo.overview)],steps:demo.steps.map(claim),documents:demo.prep.map(claim),fees:demo.fees.map(claim),deadlines:demo.deadlines.map(claim)},evidence:[],unknowns:[{kind:'unverified',category:'general',text:lang==='bn'?'এটি আগে থেকে তৈরি ডেমো; বর্তমান সরকারি শর্ত, ফি ও সময় যাচাই করা হয়নি।':'Current official requirements, fees and timing have not been checked.',evidence_ids:[]}],withheld_count:0,partial:false,has_guidance:true};
 return createRetrieval({id:'demo-'+lang+'-'+index,title:demo.title,input:demo.title,kind:'ask',language:lang,result});
}
