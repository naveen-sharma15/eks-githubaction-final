const toggle = document.getElementById("darkToggle");

if (localStorage.getItem("darkmode") === "enabled") {
    document.body.classList.add("dark");
    toggle.checked = true;
}

toggle.addEventListener("change", () => {
    if (toggle.checked) {
        document.body.classList.add("dark");
        localStorage.setItem("darkmode", "enabled");
    } else {
        document.body.classList.remove("dark");
        localStorage.setItem("darkmode", "disabled");
    }
});
