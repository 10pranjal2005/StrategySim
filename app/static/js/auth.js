document.addEventListener("DOMContentLoaded", function () {

    const toggleButtons = document.querySelectorAll(
        "[data-password-toggle]"
    );

    toggleButtons.forEach(function (button) {

        button.addEventListener("click", function () {

            const targetId = button.getAttribute("data-target");
            const passwordInput = document.getElementById(targetId);

            if (!passwordInput) {
                return;
            }

            const isPasswordHidden =
                passwordInput.type === "password";

            passwordInput.type = isPasswordHidden
                ? "text"
                : "password";

            button.setAttribute(
                "aria-label",
                isPasswordHidden
                    ? "Hide password"
                    : "Show password"
            );

            button.setAttribute(
                "aria-pressed",
                isPasswordHidden ? "true" : "false"
            );

            button.innerHTML = isPasswordHidden
                ? `
                    <svg viewBox="0 0 24 24" aria-hidden="true">
                        <path d="M3 3l18 18"></path>
                        <path d="M10.6 10.6a2 2 0 0 0 2.8 2.8"></path>
                        <path d="M9.9 5.2A10.8 10.8 0 0 1 12 5c5.5 0 9 7 9 7a14 14 0 0 1-3.1 3.9"></path>
                        <path d="M6.2 6.2C3.9 7.8 3 12 3 12s3.5 7 9 7a9.8 9.8 0 0 0 3.1-.5"></path>
                    </svg>
                `
                : `
                    <svg viewBox="0 0 24 24" aria-hidden="true">
                        <path d="M2.5 12s3.5-7 9.5-7 9.5 7 9.5 7-3.5 7-9.5 7-9.5-7-9.5-7Z"></path>
                        <circle cx="12" cy="12" r="3"></circle>
                    </svg>
                `;

        });

    });

});