import 'fake-indexeddb/auto';
import {webcrypto} from 'node:crypto';
import {cleanup,render,screen,waitFor} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {afterEach,beforeAll,beforeEach,expect,it,vi} from 'vitest';
import {clearWorkspace} from './localStore';
import {PRODUCT_COPY} from './productCopy';
const mocks=vi.hoisted(()=>({sso:vi.fn(),getToken:vi.fn(),signOut:vi.fn(),loaded:true,userId:null as string|null,tokens:[] as (()=>Promise<string|null>)[]}));
vi.mock('@clerk/react',()=>({ClerkProvider:({children}:any)=>children,ClerkLoaded:({children}:any)=>children,ClerkLoading:()=>null,ClerkFailed:()=>null,HandleSSOCallback:()=>null,useAuth:()=>({isLoaded:mocks.loaded,userId:mocks.userId,getToken:mocks.getToken}),useUser:()=>({user:null}),useClerk:()=>({signOut:mocks.signOut}),useSignIn:()=>({signIn:{sso:mocks.sso}})}));
vi.mock('./cloudStore',()=>({createCloudStore:(_url:string,_key:string,token:()=>Promise<string|null>)=>{mocks.tokens.push(token);return {pull:vi.fn(async()=>({retrievals:[],tasks:[],outbox:[]})),apply:vi.fn()}}}));
let AccountRoot:typeof import('./AccountRoot').AccountRoot;
beforeAll(async()=>{vi.stubEnv('VITE_CLOUD_ENABLED','true');vi.stubEnv('VITE_CLERK_PUBLISHABLE_KEY','pk_test_fixture');vi.stubEnv('VITE_SUPABASE_URL','https://example.supabase.co');vi.stubEnv('VITE_SUPABASE_PUBLISHABLE_KEY','public-fixture');AccountRoot=(await import('./AccountRoot')).AccountRoot});
beforeEach(async()=>{vi.stubGlobal('crypto',webcrypto);history.replaceState(null,'','#home');localStorage.clear();await clearWorkspace('guest');mocks.loaded=true;mocks.userId=null;mocks.tokens=[];mocks.getToken.mockReset();mocks.sso.mockReset();mocks.sso.mockResolvedValue({error:null})});
afterEach(()=>{cleanup();vi.restoreAllMocks();vi.unstubAllGlobals()});
it('starts Google OAuth with an explicit callback and exposes recoverable failures',async()=>{
 const user=userEvent.setup();render(<AccountRoot/>);await screen.findByRole('heading',{name:PRODUCT_COPY.en.hero});
 await user.click(screen.getByRole('button',{name:PRODUCT_COPY.en.signIn}));expect(mocks.sso).toHaveBeenCalledWith({strategy:'oauth_google',redirectUrl:location.origin+'/#home',redirectCallbackUrl:location.origin+'/sso-callback'});
 mocks.sso.mockResolvedValueOnce({error:{code:'offline_signin_failure'}});vi.spyOn(console,'warn').mockImplementation(()=>{});
 await user.click(screen.getByRole('button',{name:PRODUCT_COPY.en.signIn}));await waitFor(()=>expect(screen.getByRole('alert').textContent).toBe(PRODUCT_COPY.en.signInFailed));
});

it('refuses old-account credentials both before and after a pending token request',async()=>{
 mocks.userId='test_one';let finish:(value:string)=>void=()=>{};mocks.getToken.mockReturnValueOnce(new Promise(resolve=>{finish=resolve}));
 const view=render(<AccountRoot/>);await screen.findByRole('heading',{name:PRODUCT_COPY.en.hero});
 const oldToken=mocks.tokens[mocks.tokens.length-1];const pending=oldToken();const rejected=expect(pending).rejects.toThrow('account_changed');
 mocks.userId='test_two';view.rerender(<AccountRoot/>);finish('old-account-token');await rejected;
 await expect(oldToken()).rejects.toThrow('account_changed');expect(mocks.getToken).toHaveBeenCalledTimes(1);
});

it('renders guest work while Clerk loads and preserves the draft when signed-out initialization completes',async()=>{
 mocks.loaded=false;const user=userEvent.setup();const view=render(<AccountRoot/>);
 await screen.findByRole('heading',{name:PRODUCT_COPY.en.hero});
 const query=screen.getByRole('textbox',{name:PRODUCT_COPY.en.query});await user.type(query,'Keep this guest draft');
 expect(screen.getByRole('button',{name:PRODUCT_COPY.en.signIn})).toHaveProperty('disabled',true);
 mocks.loaded=true;view.rerender(<AccountRoot/>);
 expect(screen.getByRole('textbox',{name:PRODUCT_COPY.en.query})).toBe(query);expect(query).toHaveProperty('value','Keep this guest draft');
 expect(screen.getByRole('button',{name:PRODUCT_COPY.en.signIn})).toHaveProperty('disabled',false);
});
