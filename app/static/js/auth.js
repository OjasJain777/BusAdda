document.querySelectorAll("[data-show-password]").forEach((button) => {
  button.addEventListener("click", () => {
    const input = button.previousElementSibling;
    const reveal = input.type === "password";
    input.type = reveal ? "text" : "password";
    button.setAttribute("aria-label", reveal ? "Hide password" : "Show password");
    button.setAttribute("aria-pressed", String(reveal));
  });
});
const confirmation = document.querySelector('[name="confirmation"]');
const password = document.querySelector('[name="password"]');
if (confirmation) {
  const check = () => confirmation.setCustomValidity(
    confirmation.value && confirmation.value !== password.value ? "The passwords do not match." : "",
  );
  confirmation.addEventListener("input", check);
  password.addEventListener("input", check);
}
