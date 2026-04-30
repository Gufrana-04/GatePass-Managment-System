document.getElementById("loginForm").addEventListener("submit", async function(e) {
    e.preventDefault();

    const data = {
        username: username.value,
        password: password.value,
        site_code: site.value
    };

    const res = await fetch("/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data)
    });

    const result = await res.json();

    if (result.status === "success") {
        window.location.href = result.redirect;
    } else {
        alert(result.message);
    }
});
