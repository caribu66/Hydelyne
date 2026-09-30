import { ApolloClient, InMemoryCache, HttpLink, from } from '@apollo/client'
import { onError } from '@apollo/client/link/error'
import { GRAPHQL_URL } from '../config'

const TOKEN_KEY = 'hydenlyne_token'

export function clearLegacyAuthToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY)
    sessionStorage.removeItem(TOKEN_KEY)
  } catch {
    // Ignore storage errors; the HttpOnly session cookie remains authoritative.
  }
}

const httpLink = new HttpLink({
  uri: GRAPHQL_URL,
  credentials: 'include',
  headers: {
    'Content-Type': 'application/json',
  },
})

const errorLink = onError(({ graphQLErrors, networkError, operation }) => {
  const unauthenticated = graphQLErrors?.some(
    (e) => (e.extensions?.code as string) === 'UNAUTHENTICATED' || /Authentication/i.test(e.message)
  )
  if (unauthenticated && operation.operationName !== 'Me') {
    clearLegacyAuthToken()
    window.dispatchEvent(new CustomEvent('hydenlyne:session-expired'))
  }
  if (networkError) {
    // Keep response bodies, URLs, and provider details out of the browser
    // console; Apollo network errors can carry the raw HTTP response.
    console.warn('[apollo] network error')
  }
})

export const apolloClient = new ApolloClient({
  link: from([errorLink, httpLink]),
  cache: new InMemoryCache(),
  defaultOptions: {
    watchQuery: { fetchPolicy: 'cache-and-network', errorPolicy: 'all' },
    query: { fetchPolicy: 'network-only', errorPolicy: 'all' },
  },
})
