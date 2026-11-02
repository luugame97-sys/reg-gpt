import { onBeforeUnmount, ref } from 'vue'

// Same breakpoint as the account/UPI cards; no duplicated table selections.
export function useMobileView() {
  const query = window.matchMedia('(max-width: 680px)')
  const mobile = ref(query.matches)
  const update = event => { mobile.value = event.matches }
  query.addEventListener('change', update)
  onBeforeUnmount(() => query.removeEventListener('change', update))
  return mobile
}
