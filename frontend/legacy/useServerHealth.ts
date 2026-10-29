import {useCallback,useEffect,useRef,useState} from 'react';
export function useServerHealth(ping:()=>Promise<unknown>){
 const [state,setState]=useState<'idle'|'waking'|'offline'>('idle');
 const confirmed=useRef(0);
 useEffect(()=>{
  let disposed=false,hiddenAt=document.visibilityState==='hidden'?Date.now():0,inFlight:Promise<void>|null=null;
  let delay:ReturnType<typeof setTimeout>|undefined;
  const wake=()=>{
   if(inFlight)return inFlight;
   const version=confirmed.current;
   delay=setTimeout(()=>{if(!disposed&&version===confirmed.current)setState('waking')},2000);
   inFlight=ping().then(()=>{if(!disposed)setState('idle')},()=>{if(!disposed&&version===confirmed.current)setState('offline')})
    .finally(()=>{clearTimeout(delay);inFlight=null});
   return inFlight;
  };
  const visible=()=>{if(document.visibilityState==='hidden'){hiddenAt=Date.now();return}if(hiddenAt&&Date.now()-hiddenAt>600000)void wake();hiddenAt=0};
  void wake();document.addEventListener('visibilitychange',visible);
  return()=>{disposed=true;clearTimeout(delay);document.removeEventListener('visibilitychange',visible)};
 },[ping]);
 const markHealthy=useCallback(()=>{confirmed.current++;setState('idle')},[]);
 return {state,markHealthy};
}
