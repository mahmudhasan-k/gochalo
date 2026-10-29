import {useMemo,useRef,useState} from 'react';
import {ClerkProvider,HandleSSOCallback,useAuth,useClerk,useUser,useSignIn} from '@clerk/react';
import {createCloudStore} from './cloudStore';
import {WorkspaceApp} from './WorkspaceApp';
const key=import.meta.env.VITE_CLERK_PUBLISHABLE_KEY,url=import.meta.env.VITE_SUPABASE_URL,databaseKey=import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY;
function AuthenticatedWorkspace(){
 const {isLoaded,userId,getToken}=useAuth(),{user}=useUser(),clerk=useClerk();const identity=useRef({userId,getToken});identity.current={userId,getToken};
 const {signIn}=useSignIn();const [authError,setAuthError]=useState(false);
 const cloud=useMemo(()=>{const owner=userId;return createCloudStore(url,databaseKey,async()=>{
  if(!owner||identity.current.userId!==owner)throw new Error('account_changed');
  const value=await identity.current.getToken();
  if(identity.current.userId!==owner)throw new Error('account_changed');
  return value;
 })},[userId]);
 const account=useMemo(()=>userId?{id:userId,name:user?.firstName||user?.username||'Account',cloud,signOut:async()=>{await clerk.signOut()}}:null,[userId,user?.firstName,user?.username,cloud,clerk]);
 if(location.pathname==='/sso-callback')return <HandleSSOCallback navigateToApp={({decorateUrl})=>location.assign(decorateUrl('/#home'))} navigateToSignIn={()=>{location.replace('/#home')}} navigateToSignUp={()=>{location.replace('/#home')}}/>;
 return <WorkspaceApp key={userId||'guest'} account={account} accountLoading={!isLoaded} signInError={authError} onSignIn={()=>{setAuthError(false);void signIn.sso({strategy:'oauth_google',redirectUrl:location.origin+'/#home',redirectCallbackUrl:location.origin+'/sso-callback'}).then(value=>{if(value.error){console.warn('Gochalo sign-in unavailable');setAuthError(true)}}).catch(()=>{console.warn('Gochalo sign-in unavailable');setAuthError(true)})}}/>;
}
export function AccountRoot(){

 if(import.meta.env.VITE_CLOUD_ENABLED!=='true'||!key||!url||!databaseKey)return <WorkspaceApp/>;

 return <ClerkProvider publishableKey={key}><AuthenticatedWorkspace/></ClerkProvider>;
}
