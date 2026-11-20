import Link from 'next/link';
import {Icon} from '@/components/icon';
export default function NotFound(){return <main className="not-found-page"><Link href="/" aria-label="Suhail Health home"><img src="/brand/logo-original.png" alt="Suhail Health"/></Link><div className="not-found-symbol"><Icon name="git-branch" size={36}/></div><p className="eyebrow">A DIFFERENT PATH</p><h1>Let’s get you<br/>back to care.</h1><p>This page could not be found. Open your workspace to find your next step.</p><Link className="button" href="/">Open Suhail Health <Icon name="arrow-right" size={17}/></Link></main>}
