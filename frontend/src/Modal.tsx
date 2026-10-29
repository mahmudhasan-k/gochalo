import {useEffect,useRef,type ReactNode} from 'react';
export function Modal({title,onClose,children}:{title:string;onClose:()=>void;children:ReactNode}){
 const ref=useRef<HTMLDialogElement>(null),close=useRef(onClose);close.current=onClose;
 useEffect(()=>{const active=document.activeElement as HTMLElement|null;const dialog=ref.current;if(dialog?.showModal)dialog.showModal();else dialog?.setAttribute('open','');return()=>{dialog?.close?.();active?.focus()}},[]);
 return <dialog ref={ref} className="product-dialog" aria-label={title} onCancel={event=>{event.preventDefault();close.current()}}><div className="dialog-head"><h2>{title}</h2><button type="button" aria-label="Close / বন্ধ করুন" onClick={onClose}>×</button></div>{children}</dialog>;
}
