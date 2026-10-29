import type {Claim} from './productTypes';
export const SOURCE_RECOVERY_COPY={en:{edit:'Edit extracted text'},bn:{edit:'নেওয়া লেখাটি সম্পাদনা করুন'}};
export function supportLabel(item:Claim,lang:'bn'|'en'){
 const bn=lang==='bn';
 switch(item.support_status){
  case 'planning_suggestion':return bn?'পরামর্শমূলক পরবর্তী ধাপ':'Suggested next step';
  case 'unreviewed':return '';
  case 'source_supported':return bn?'দেওয়া উৎসের ভিত্তিতে':'Based on the supplied source';
  case 'web_cited':return bn?'ওয়েব উৎস উল্লেখ আছে':'Web source cited';
  default:return '';
 }
}
