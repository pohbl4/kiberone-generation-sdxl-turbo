export function redirectToLogin() {
  if (typeof window === "undefined") {
    return;
  }
  if (window.location.pathname === "/login") {
    return;
  }
  window.location.href = "/login";
}

export function redirectIfUnauthorized(response: Response): boolean {
  if (response.status === 401) {
    redirectToLogin();
    return true;
  }
  return false;
}
