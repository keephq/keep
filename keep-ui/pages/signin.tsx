// @ts-nocheck
import { signIn, getCsrfToken, getProviders, SessionProvider } from 'next-auth/react'
import Image from 'next/image'
import styles from './signin.module.css'

const Signin = ({ csrfToken, providers }) => {
  const auth0Provider = providers?.auth0;

  return (
    <div style={{ overflow: 'hidden', position: 'relative' }}>
      <div className={styles.wrapper} />
      <div className={styles.content}>
        <div className={styles.cardWrapper}>
          <Image src='/keep.svg' width="196" height="64" alt='App Logo' style={{ height: '150px', marginBottom: '20px' }} />
          <div className={styles.cardContent}>
            {auth0Provider &&
              <button onClick={() => signIn(auth0Provider.id, { callbackUrl: '/' })} >
                Sign in to Keep
              </button>
            }
          </div>
        </div>
      </div>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src='/login_pattern.svg' alt='Pattern Background' layout='fill' className={styles.styledPattern} />
    </div>
  )
}

export default Signin

export async function getServerSideProps(context) {
  const providers = await getProviders()
  const csrfToken = await getCsrfToken(context)
  return {
    props: {
      providers,
      csrfToken
    },
  }
}
