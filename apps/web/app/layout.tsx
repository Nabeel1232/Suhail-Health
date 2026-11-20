import type { Metadata } from 'next';
import './globals.css';
import './care.css';
import './workspaces.css';
import './patient.css';
import './context-chat.css';
export const metadata: Metadata = {metadataBase:new URL(process.env.APP_ORIGIN||'http://localhost:3000'),title:'Suhail Health | Guiding every result to care', description:'Screening to care coordination, with clear ownership and clinician oversight.', openGraph:{title:'Suhail Health',description:'Guiding every result to care.',images:['/brand/social-card.svg']}, icons:{apple:'/apple-touch-icon.png'}, manifest:'/manifest.webmanifest'};
export default function RootLayout({children}:{children:React.ReactNode}) { return <html lang="en"><body>{children}</body></html>; }
