import React from 'react';
import {createRoot} from 'react-dom/client';
import {AccountRoot} from './AccountRoot';
export {WorkspaceApp as App} from './WorkspaceApp';
const mount=document.getElementById('root');
if(mount)createRoot(mount).render(<React.StrictMode><AccountRoot/></React.StrictMode>);
