import { ApolloClient, InMemoryCache, HttpLink, from } from '@apollo/client'
import { setContext } from '@apollo/client/link/context'
import { onError } from '@apollo/client/link/error'
import { GRAPHQL_URL } from '../config'

const TOKEN_KEY = 'hydenlyne_token'

export function getAuthToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY) || sessionStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function setAuthToken(token: string | null, remember = true) {
  try {
    localStorage.removeItem(TOKEN_KEY)
    sessionStorage.removeItem(TOKEN_KEY)
    if (token) (remember ? localStorage : sessionStorage).setItem(TOKEN_KEY, token)
  } catch {
    // ignore storage errors
  }
}

const httpLink = new HttpLink({
  uri: GRAPHQL_URL,
  credentials: 'include',
  headers: {
    'Content-Type': 'application/json',
  },
})

const authLink = setContext((_, { headers }) => {
  const token = getAuthToken()
  return {
    headers: {
      ...headers,
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  }
})

const errorLink = onError(({ graphQLErrors, networkError }) => {
  const unauthenticated = graphQLErrors?.some(
    (e) => (e.extensions?.code as string) === 'UNAUTHENTICATED' || /Authentication/i.test(e.message)
  )
  if (unauthenticated) {
    // Only act if we actually had a token — otherwise (e.g. first visit on the
    // login screen) this is just the "not signed in yet" case and is silent.
    const hadToken = getAuthToken()
    if (hadToken) {
      setAuthToken(null)
      console.warn('[apollo] session expired — token cleared')
      window.dispatchEvent(new CustomEvent('hydenlyne:session-expired'))
    }
  }
  if (networkError) {
    console.warn('[apollo] network error', networkError)
  }
})

export const apolloClient = new ApolloClient({
  link: from([errorLink, authLink, httpLink]),
  cache: new InMemoryCache(),
  defaultOptions: {
    watchQuery: { fetchPolicy: 'cache-and-network', errorPolicy: 'all' },
    query: { fetchPolicy: 'network-only', errorPolicy: 'all' },
  },
})
