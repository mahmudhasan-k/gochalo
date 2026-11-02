import {createRetrieval,type Lang,type PlanResult} from './productTypes';
// Authored source summaries checked 2 November 2026; prepared demos, not live model review.
const demos={
  "en": [
    {
      "title": "How do I apply for an Australian visa from Bangladesh?",
      "chipLabel": "Australian visitor visa",
      "category": "Travel",
      "overview": "(Pre-made demo) For an adult Bangladeshi passport holder visiting for tourism or family, using Visitor visa subclass 600, Tourist stream outside Australia. Stay outside Australia when applying and when a decision is made. Work is not allowed; this is not a student or work visa.",
      "steps": [
        "Create or sign in to ImmiAccount and choose Visitor visa 600 — Tourist stream, outside Australia.",
        "Complete the form and upload identity, visit-purpose and financial evidence relevant to your circumstances.",
        "Upload non-English records together with their English translations.",
        "Pay the displayed visa charge and submit; keep your reference number. Each family member needs a separate application.",
        "If Home Affairs sends a biometrics request, follow the letter and arrange collection through VFS Global in Bangladesh. Complete other checks if requested.",
        "Monitor ImmiAccount messages and read the decision and conditions before finalising travel."
      ],
      "prep": [
        "Valid passport and identity records requested in ImmiAccount",
        "Evidence explaining the visit and your circumstances at home",
        "Evidence of sufficient funds for the stay",
        "Original-language documents plus English translations where needed",
        "Biometrics request letter, if issued; further health/character evidence if requested"
      ],
      "fees": [
        "Published base visa charge: from AUD 250 per applicant for this stream. Confirm the displayed charge when submitting.",
        "Biometrics, health checks and police certificates may add costs; these are separate from the base visa charge."
      ],
      "deadlines": [
        "Plan to apply at least one month before travel: official visitor guidance recommends this lead time, not a guaranteed processing period.",
        "Complete requested checks by the date in the official request letter.",
        "The grant letter sets permitted stay and entry conditions; stay length is assessed individually."
      ],
      "sources": [
        {
          "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600/tourist-stream-overseas?bk=HowTo",
          "title": "Home Affairs — Visitor 600, Tourist stream outside Australia"
        },
        {
          "url": "https://bangladesh.highcommission.gov.au/daca/Visas_and_Migration.html",
          "title": "Australian High Commission Bangladesh — Online applications and biometrics"
        },
        {
          "url": "https://peru.embassy.gov.au/lima/apply.html",
          "title": "Australian Embassy — Uploading evidence and translations"
        },
        {
          "url": "https://singapore.embassy.gov.au/sing/visas-faq.html",
          "title": "Australian High Commission — Visitor application lead time"
        }
      ],
      "notes": []
    },
    {
      "title": "How do I apply for an e-passport in Bangladesh?",
      "chipLabel": "Bangladesh e-passport",
      "category": "Travel",
      "overview": "(Pre-made demo) Apply for an e-passport online, pay the fee and complete biometric enrolment at your passport office. This example covers an application inside Bangladesh, with fees for a 48-page, five-year passport. The documents you bring depend on your age and circumstances; other passport options and applications abroad follow different fees or requirements.",
      "steps": [
        "Open epassport.gov.bd and select Apply Online for e-Passport / Re-Issue.",
        "Complete the online form using the applicable NID or English-version birth-registration record; check names and dates.",
        "Choose the passport and delivery options, then pay using a listed online provider or bank A-Challan.",
        "Print the application and follow the portal’s enrolment instructions; bring the applicable originals and copies for biometrics.",
        "Keep the delivery slip and use it when collecting your passport."
      ],
      "prep": [
        "Printed online application form",
        "Applicable English birth-registration record; NID original and copy for applicants over 20",
        "A-Challan receipt for offline fee payment",
        "Further documents for your circumstances: use the official enrolment checklist",
        "For collection: delivery slip; previous passport for reissue. Under-12 child: parent’s NID/passport; collection by another person: signed authority and collector’s NID."
      ],
      "fees": [
        "Regular: BDT 4,025, including 15% VAT.",
        "Express: BDT 6,325, including 15% VAT.",
        "Super Express: BDT 8,625, including 15% VAT.",
        "Government employees with NOC/PRL documents: Express at Regular fees; Super Express at Express fees."
      ],
      "deadlines": [
        "From biometric enrolment: Regular within 15 working days / 21 days; Express within 7 working days / 10 days; Super Express within 2 working days."
      ],
      "sources": [
        {
          "url": "https://www.epassport.gov.bd/instructions/passport-fees",
          "title": "Bangladesh e-Passport — Fees, payments and delivery windows"
        },
        {
          "url": "https://file-dhaka.portal.gov.bd/uploads/20d153bc-c5de-4496-8c9c-598c79e38fc6/641/977/31e/64197731e2bfc705001666.pdf",
          "title": "Government fee schedule — Domestic fees including VAT"
        },
        {
          "url": "https://epassport.gov.bd/",
          "title": "Bangladesh e-Passport — Apply online"
        },
        {
          "url": "https://www.epassport.gov.bd/landing/notices/160",
          "title": "Bangladesh e-Passport — Enrolment checklist"
        },
        {
          "url": "https://www.epassport.gov.bd/landing/faqs/272",
          "title": "Bangladesh e-Passport — Collection documents"
        },
        {
          "url": "https://www.epassport.gov.bd/instructions/instructions",
          "title": "Bangladesh e-Passport — Application instructions"
        }
      ],
      "notes": []
    },
    {
      "title": "How do I apply for Dhaka University admission?",
      "chipLabel": "Dhaka University admission",
      "category": "Education",
      "overview": "(Pre-made demo) Apply to Dhaka University by completing the online form, uploading your photograph and paying the unit application fee. Then download your admit card, check your seat plan and attend the admission test.",
      "steps": [
        "Check eligibility for the 2025–26 Science Unit: a science-group applicant with SSC in 2020–23, HSC in 2025, and a combined GPA of at least 8.0 with 3.5 in each exam, including the fourth subject.",
        "Open the DU admission portal and enter your SSC/HSC board, roll and passing-year information.",
        "Add your address, mobile number, exam-centre division and any applicable quota details; upload the specified photograph. A parent’s NID number is optional.",
        "Pay BDT 1,050 online or through Sonali, Janata, Agrani or Rupali Bank, then retain the confirmation.",
        "Download the admit card and check the published seat plan 48 hours before the exam.",
        "Take your admit card and sit in your assigned seat at least 30 minutes before the Science Unit test."
      ],
      "prep": [
        "Digital photograph in the size specified by the admission portal",
        "Admit card for the test",
        "Quota documentation, if applying under a quota"
      ],
      "fees": [
        "Science Unit application fee for 2025–26: BDT 1,050."
      ],
      "deadlines": [
        "Applications opened: 29 October 2025, noon (Dhaka).",
        "Final application/payment deadline: 19 November 2025, 11:59 pm, after extension from 16 November.",
        "Science Unit test: 20 December 2025, 11:00 am–12:30 pm; be seated by 10:30 am."
      ],
      "sources": [
        {
          "url": "https://www.du.ac.bd/du_post_details/news/25400",
          "title": "DU — 2025–26 admission announcement"
        },
        {
          "url": "https://admission.eis.du.ac.bd/bn/408b7c8ad06e4d9954fa2d948a01f508/5524202192_1",
          "title": "DU — Archived final application schedule"
        },
        {
          "url": "https://duadmission.com/wp-content/uploads/2025/11/KA-Unit.pdf",
          "title": "DU Science Unit 2025–26 guide (archived mirror)"
        },
        {
          "url": "https://tbsgraduates.net/bangla/bn-education/bn-ugadmission/duadmission2025-26/",
          "title": "TBS Graduates — Published 2025–26 unit fees"
        }
      ],
      "notes": []
    }
  ],
  "bn": [
    {
      "title": "বাংলাদেশ থেকে অস্ট্রেলিয়ার ভিসার জন্য কীভাবে আবেদন করব?",
      "chipLabel": "অস্ট্রেলিয়ার ভ্রমণ ভিসা",
      "category": "Travel",
      "overview": "(আগে থেকে তৈরি ডেমো) প্রাপ্তবয়স্ক বাংলাদেশি পাসপোর্টধারীর পর্যটন বা পরিবার দেখার জন্য Visitor visa subclass 600, Tourist stream outside Australia। আবেদন ও সিদ্ধান্তের সময় অস্ট্রেলিয়ার বাইরে থাকতে হবে। কাজ করা যাবে না; এটি শিক্ষার্থী বা কাজের ভিসা নয়।",
      "steps": [
        "ImmiAccount খুলুন বা প্রবেশ করুন। Visitor visa 600 — Tourist stream, outside Australia বেছে নিন।",
        "ফরম পূরণ করে নিজের পরিস্থিতি অনুযায়ী পরিচয়, ভ্রমণের উদ্দেশ্য ও অর্থের প্রমাণ দিন।",
        "ইংরেজি নয় এমন নথির সঙ্গে ইংরেজি অনুবাদও দিন।",
        "দেখানো ভিসা ফি দিয়ে জমা করুন ও আবেদনের নম্বর রাখুন। পরিবারের প্রত্যেকের আলাদা আবেদন লাগবে।",
        "Home Affairs বায়োমেট্রিক চাইলে চিঠির নির্দেশনা মেনে বাংলাদেশে VFS Global-এর মাধ্যমে দিন। অন্য পরীক্ষা চাইলে সম্পন্ন করুন।",
        "ImmiAccount-এর বার্তা দেখুন। ভ্রমণ চূড়ান্ত করার আগে সিদ্ধান্ত ও ভিসার শর্ত পড়ুন।"
      ],
      "prep": [
        "বৈধ পাসপোর্ট ও ImmiAccount-এ চাওয়া পরিচয়ের নথি",
        "ভ্রমণের উদ্দেশ্য ও দেশে নিজের পরিস্থিতির প্রমাণ",
        "থাকার খরচ বহনের সামর্থ্যের প্রমাণ",
        "প্রয়োজন হলে মূল ভাষার নথি ও ইংরেজি অনুবাদ",
        "ইস্যু হলে বায়োমেট্রিকের অনুরোধপত্র; চাইলে স্বাস্থ্য বা চরিত্রসংক্রান্ত বাড়তি প্রমাণ"
      ],
      "fees": [
        "এই ভিসার প্রকাশিত মূল ফি: প্রতি আবেদনকারীর জন্য ২৫০ অস্ট্রেলীয় ডলার থেকে। জমার সময় দেখানো ফি মিলিয়ে নিন।",
        "বায়োমেট্রিক, স্বাস্থ্য পরীক্ষা ও পুলিশ সনদে বাড়তি খরচ হতে পারে; এগুলো মূল ভিসা ফির বাইরে।"
      ],
      "deadlines": [
        "ভ্রমণের অন্তত এক মাস আগে আবেদনের পরিকল্পনা করুন—সরকারি নির্দেশনার পরামর্শ, নিশ্চিত নিষ্পত্তির সময় নয়।",
        "সরকারি অনুরোধপত্রে দেওয়া সময়ের মধ্যে চাওয়া পরীক্ষা বা তথ্য দিন।",
        "অনুমোদনপত্রে থাকার সময় ও প্রবেশের শর্ত থাকবে; থাকার মেয়াদ ব্যক্তিভেদে নির্ধারিত হয়।"
      ],
      "sources": [
        {
          "url": "https://immi.homeaffairs.gov.au/visas/getting-a-visa/visa-listing/visitor-600/tourist-stream-overseas?bk=HowTo",
          "title": "Home Affairs — Visitor 600, Tourist stream outside Australia"
        },
        {
          "url": "https://bangladesh.highcommission.gov.au/daca/Visas_and_Migration.html",
          "title": "Australian High Commission Bangladesh — Online applications and biometrics"
        },
        {
          "url": "https://peru.embassy.gov.au/lima/apply.html",
          "title": "Australian Embassy — Uploading evidence and translations"
        },
        {
          "url": "https://singapore.embassy.gov.au/sing/visas-faq.html",
          "title": "Australian High Commission — Visitor application lead time"
        }
      ],
      "notes": []
    },
    {
      "title": "বাংলাদেশে ই-পাসপোর্টের জন্য কীভাবে আবেদন করব?",
      "chipLabel": "বাংলাদেশের ই-পাসপোর্ট",
      "category": "Travel",
      "overview": "(আগে থেকে তৈরি ডেমো) ই-পাসপোর্টের জন্য অনলাইনে আবেদন করে ফি দিন, তারপর পাসপোর্ট অফিসে বায়োমেট্রিক সম্পন্ন করুন। এই উদাহরণে দেশের ভেতরে আবেদন এবং ৪৮ পৃষ্ঠা, পাঁচ বছর মেয়াদি পাসপোর্টের ফি দেখানো হয়েছে। বয়স ও পরিস্থিতি অনুযায়ী সঙ্গে নেওয়ার নথি বদলাবে; অন্য পাসপোর্টের ধরন বা বিদেশে আবেদনে ফি ও শর্ত আলাদা হতে পারে।",
      "steps": [
        "epassport.gov.bd-তে Apply Online for e-Passport / Re-Issue বেছে নিন।",
        "প্রযোজ্য এনআইডি বা ইংরেজি জন্মনিবন্ধন অনুযায়ী ফরম পূরণ করে নাম ও তারিখ মিলিয়ে নিন।",
        "পাসপোর্ট ও ডেলিভারির ধরন বেছে তালিকাভুক্ত অনলাইন মাধ্যমে বা ব্যাংকের এ-চালানে ফি দিন।",
        "আবেদন ছাপিয়ে পোর্টালের এনরোলমেন্ট নির্দেশনা অনুসরণ করুন। বায়োমেট্রিকের জন্য প্রযোজ্য মূল নথি ও কপি নিন।",
        "ডেলিভারি স্লিপ রাখুন এবং সংগ্রহের সময়ে সঙ্গে নিন।"
      ],
      "prep": [
        "অনলাইন আবেদনপত্রের প্রিন্ট",
        "প্রযোজ্য ইংরেজি জন্মনিবন্ধন; ২০ বছরের বেশি হলে এনআইডির মূল ও কপি",
        "অফলাইনে ফি দিলে চালানের রসিদ",
        "নিজের পরিস্থিতির বাড়তি নথি: সরকারি এনরোলমেন্ট চেকলিস্ট অনুসরণ করুন",
        "সংগ্রহে: ডেলিভারি স্লিপ; পুনঃইস্যুতে পুরোনো পাসপোর্ট। ১২ বছরের কম শিশুর জন্য অভিভাবকের এনআইডি/পাসপোর্ট; অন্যকে দিয়ে সংগ্রহে স্বাক্ষরিত অনুমতি ও সংগ্রহকারীর এনআইডি।"
      ],
      "fees": [
        "Regular: ৪,০২৫ টাকা, ১৫% ভ্যাটসহ।",
        "Express: ৬,৩২৫ টাকা, ১৫% ভ্যাটসহ।",
        "Super Express: ৮,৬২৫ টাকা, ১৫% ভ্যাটসহ।",
        "NOC/PRL নথি থাকা সরকারি কর্মচারী: Regular ফিতে Express; Express ফিতে Super Express সুবিধা।"
      ],
      "deadlines": [
        "বায়োমেট্রিক থেকে: Regular ১৫ কার্যদিবস/২১ দিনের মধ্যে; Express ৭ কার্যদিবস/১০ দিনের মধ্যে; Super Express ২ কার্যদিবসের মধ্যে।"
      ],
      "sources": [
        {
          "url": "https://www.epassport.gov.bd/instructions/passport-fees",
          "title": "Bangladesh e-Passport — Fees, payments and delivery windows"
        },
        {
          "url": "https://file-dhaka.portal.gov.bd/uploads/20d153bc-c5de-4496-8c9c-598c79e38fc6/641/977/31e/64197731e2bfc705001666.pdf",
          "title": "Government fee schedule — Domestic fees including VAT"
        },
        {
          "url": "https://epassport.gov.bd/",
          "title": "Bangladesh e-Passport — Apply online"
        },
        {
          "url": "https://www.epassport.gov.bd/landing/notices/160",
          "title": "Bangladesh e-Passport — Enrolment checklist"
        },
        {
          "url": "https://www.epassport.gov.bd/landing/faqs/272",
          "title": "Bangladesh e-Passport — Collection documents"
        },
        {
          "url": "https://www.epassport.gov.bd/instructions/instructions",
          "title": "Bangladesh e-Passport — Application instructions"
        }
      ],
      "notes": []
    },
    {
      "title": "ঢাকা বিশ্ববিদ্যালয়ে ভর্তির জন্য কীভাবে আবেদন করব?",
      "chipLabel": "ঢাকা বিশ্ববিদ্যালয়ে ভর্তি",
      "category": "Education",
      "overview": "(আগে থেকে তৈরি ডেমো) ঢাকা বিশ্ববিদ্যালয়ে আবেদন করতে অনলাইন ফরম পূরণ, ছবি আপলোড ও ইউনিটের আবেদন ফি পরিশোধ করতে হয়। এরপর প্রবেশপত্র নামিয়ে আসনবিন্যাস দেখে ভর্তি পরীক্ষায় অংশ নিন।",
      "steps": [
        "২০২৫–২৬ বিজ্ঞান ইউনিটের যোগ্যতা মিলিয়ে নিন: বিজ্ঞান শাখা, এসএসসি ২০২০–২৩, এইচএসসি ২০২৫ এবং চতুর্থ বিষয়সহ মোট জিপিএ অন্তত ৮.০, প্রতিটিতে ৩.৫।",
        "ঢাবির ভর্তি পোর্টালে এসএসসি/এইচএসসির বোর্ড, রোল ও পাসের বছর দিন।",
        "ঠিকানা, মোবাইল, পরীক্ষাকেন্দ্রের বিভাগ ও প্রযোজ্য কোটার তথ্য দিয়ে নির্ধারিত ছবি আপলোড করুন। বাবা/মায়ের এনআইডি নম্বর ঐচ্ছিক।",
        "অনলাইনে বা সোনালী, জনতা, অগ্রণী বা রূপালী ব্যাংকে ১,০৫০ টাকা দিয়ে নিশ্চিতকরণ রাখুন।",
        "প্রবেশপত্র নামান। পরীক্ষার ৪৮ ঘণ্টা আগে প্রকাশিত আসনবিন্যাস দেখুন।",
        "প্রবেশপত্র নিয়ে পরীক্ষা শুরুর অন্তত ৩০ মিনিট আগে নির্ধারিত আসনে বসুন।"
      ],
      "prep": [
        "পোর্টালে নির্ধারিত মাপের ডিজিটাল ছবি",
        "পরীক্ষার প্রবেশপত্র",
        "কোটায় আবেদন করলে প্রযোজ্য নথি"
      ],
      "fees": [
        "২০২৫–২৬ বিজ্ঞান ইউনিটের আবেদন ফি: ১,০৫০ টাকা।"
      ],
      "deadlines": [
        "আবেদন শুরু: ২৯ অক্টোবর ২০২৫ দুপুর ১২টা, ঢাকা সময়।",
        "আবেদন ও ফি জমার বর্ধিত শেষ সময়: ১৯ নভেম্বর ২০২৫ রাত ১১টা ৫৯ মিনিট; প্রথমে ১৬ নভেম্বর ছিল।",
        "বিজ্ঞান ইউনিট পরীক্ষা: ২০ ডিসেম্বর ২০২৫ সকাল ১১টা–দুপুর ১২টা ৩০ মিনিট; সকাল ১০টা ৩০ মিনিটের মধ্যে আসনে বসুন।"
      ],
      "sources": [
        {
          "url": "https://www.du.ac.bd/du_post_details/news/25400",
          "title": "DU — 2025–26 admission announcement"
        },
        {
          "url": "https://admission.eis.du.ac.bd/bn/408b7c8ad06e4d9954fa2d948a01f508/5524202192_1",
          "title": "DU — Archived final application schedule"
        },
        {
          "url": "https://duadmission.com/wp-content/uploads/2025/11/KA-Unit.pdf",
          "title": "DU Science Unit 2025–26 guide (archived mirror)"
        },
        {
          "url": "https://tbsgraduates.net/bangla/bn-education/bn-ugadmission/duadmission2025-26/",
          "title": "TBS Graduates — Published 2025–26 unit fees"
        }
      ],
      "notes": []
    }
  ]
};
export function demoCatalogue(lang:Lang){return demos[lang]}
export function openDemo(lang:Lang,index:number){
 const demo=demos[lang][index];const claim=(text:string)=>({text,evidence_ids:[]});
 const sources=demo.sources.map((source,i)=>({id:'s'+(i+1),...source}));
 const result:PlanResult={review_mode:'saved_example',demo:true,semantic_review_complete:false,sections:{explanation:[claim(demo.overview)],steps:demo.steps.map(claim),documents:demo.prep.map(claim),fees:demo.fees.map(claim),deadlines:demo.deadlines.map(claim)},sources,evidence:[],unknowns:demo.notes.map(text=>({kind:'missing' as const,category:'general' as const,text,evidence_ids:[]})),withheld_count:0,partial:false,has_guidance:true};
 const input=[lang==='bn'?'প্রস্তুত ডেমোর সম্পাদিত সারাংশ; মূল উৎসের হুবহু লেখা নয়।':'Authored summary for a prepared demo; not the verbatim source text.',demo.title,demo.overview,...demo.steps,...demo.prep,...demo.fees,...demo.deadlines,...sources.map(s=>s.url)].join('\n');
 return createRetrieval({id:'demo-'+lang+'-'+index,title:demo.title,input,kind:'ask',language:lang,result});
}
