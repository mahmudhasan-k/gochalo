import {useEffect,useLayoutEffect,useState} from 'react';
export type ThemePreference='system'|'light'|'dark';
export function useTheme(defaultPreference:ThemePreference='system'){
 const [preference,setPreference]=useState<ThemePreference>(()=>{try{const v=localStorage.getItem('theme');return v==='light'||v==='dark'||v==='system'?v:defaultPreference}catch{return defaultPreference}});
 const [media]=useState(()=>typeof window.matchMedia==='function'?window.matchMedia('(prefers-color-scheme: dark)'):null);
 const [systemDark,setSystemDark]=useState(media?.matches??false);
 useEffect(()=>{if(!media)return;const changed=()=>setSystemDark(media.matches);media.addEventListener('change',changed);return()=>media.removeEventListener('change',changed)},[media]);
 const resolved=preference==='system'?(systemDark?'dark':'light'):preference;
 useLayoutEffect(()=>{document.documentElement.classList.toggle('dark',resolved==='dark');document.documentElement.style.colorScheme=resolved},[resolved]);
 useEffect(()=>{try{localStorage.setItem('theme',preference)}catch{/* Storage is optional. */}},[preference]);
 return {preference,resolved,setPreference};
}
