document.addEventListener("DOMContentLoaded", () => {
    // Tab switching
    const tabs = document.querySelectorAll(".tab");
    tabs.forEach(tab => {
        tab.addEventListener("click", () => {
            tabs.forEach(t => t.classList.remove("active"));
            document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
            tab.classList.add("active");
            document.getElementById("tab-" + tab.dataset.tab).classList.add("active");
        });
    });

    // Photo upload
    const dropZone = document.getElementById("drop-zone");
    const photoInput = document.getElementById("photo-input");
    const photoPreview = document.getElementById("photo-preview");
    const photoSubmit = document.getElementById("photo-submit");

    dropZone.addEventListener("click", () => photoInput.click());

    dropZone.addEventListener("dragover", e => {
        e.preventDefault();
        dropZone.classList.add("dragover");
    });
    dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragover"));
    dropZone.addEventListener("drop", e => {
        e.preventDefault();
        dropZone.classList.remove("dragover");
        if (e.dataTransfer.files.length) {
            photoInput.files = e.dataTransfer.files;
            showPreview(e.dataTransfer.files[0]);
        }
    });

    photoInput.addEventListener("change", () => {
        if (photoInput.files.length) showPreview(photoInput.files[0]);
    });

    function showPreview(file) {
        const reader = new FileReader();
        reader.onload = e => {
            photoPreview.src = e.target.result;
            photoPreview.hidden = false;
            photoSubmit.disabled = false;
        };
        reader.readAsDataURL(file);
    }

    // Name search
    document.getElementById("name-form").addEventListener("submit", async e => {
        e.preventDefault();
        const firstName = document.getElementById("first_name").value.trim();
        const lastName = document.getElementById("last_name").value.trim();
        if (!firstName && !lastName) return alert("Veuillez entrer un nom ou un prenom.");

        const platforms = [...document.querySelectorAll('input[name="platforms"]:checked')]
            .map(cb => cb.value);

        showLoading();
        try {
            const resp = await fetch("/search/name", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ first_name: firstName, last_name: lastName, platforms }),
            });
            const data = await resp.json();
            if (data.error) throw new Error(data.error);
            renderResults(data);
        } catch (err) {
            hideLoading();
            alert("Erreur: " + err.message);
        }
    });

    // Photo search
    document.getElementById("photo-form").addEventListener("submit", async e => {
        e.preventDefault();
        if (!photoInput.files.length) return;

        const formData = new FormData();
        formData.append("photo", photoInput.files[0]);

        showLoading();
        try {
            const resp = await fetch("/search/photo", { method: "POST", body: formData });
            const data = await resp.json();
            if (data.error) throw new Error(data.error);
            renderResults(data);
        } catch (err) {
            hideLoading();
            alert("Erreur: " + err.message);
        }
    });

    function showLoading() {
        document.getElementById("loading").hidden = false;
        document.getElementById("results").hidden = true;
    }

    function hideLoading() {
        document.getElementById("loading").hidden = true;
    }

    const PLATFORM_ICONS = {
        "GitHub": "GH",
        "Twitter / X": "X",
        "LinkedIn": "in",
        "Instagram": "IG",
        "Facebook": "FB",
    };

    function getPlatformClass(platform) {
        return platform.toLowerCase().replace(/ \/ /g, "").replace(/ /g, "");
    }

    function renderResults(data) {
        hideLoading();
        const container = document.getElementById("results");
        container.hidden = false;

        let html = '<div class="results-header">';
        html += `<h2>Resultats pour "${data.query}"</h2>`;
        html += `<p>${data.total} profil(s) trouve(s)</p>`;
        html += '</div>';

        // Platform statuses
        if (data.platform_status) {
            html += '<div class="platform-statuses">';
            for (const [platform, status] of Object.entries(data.platform_status)) {
                const cls = status === "ok" ? "ok" : status === "no_results" ? "no-results" : "error";
                const label = status === "ok" ? "OK" : status === "no_results" ? "Aucun resultat" : "Erreur";
                html += `<span class="status-badge ${cls}">${platform}: ${label}</span>`;
            }
            html += '</div>';
        }

        if (data.results.length === 0) {
            html += '<div class="no-results"><p>Aucun profil trouve. Essayez avec un autre nom ou une autre photo.</p></div>';
        } else {
            html += '<div class="results-grid">';
            for (const r of data.results) {
                const pClass = getPlatformClass(r.platform);
                const icon = PLATFORM_ICONS[r.platform] || r.platform[0];
                html += `
                <div class="result-card">
                    <div class="card-header">
                        ${r.avatar_url
                            ? `<img class="card-avatar" src="${r.avatar_url}" alt="${r.display_name}">`
                            : `<div class="card-avatar-placeholder">${icon}</div>`
                        }
                        <div class="card-info">
                            <div class="card-name">${escapeHtml(r.display_name)}</div>
                            <div class="card-username">${escapeHtml(r.username)}</div>
                        </div>
                    </div>
                    ${r.bio ? `<div class="card-bio">${escapeHtml(r.bio)}</div>` : ''}
                    <div class="card-footer">
                        <span class="card-platform ${pClass}">${r.platform}</span>
                        <a class="card-link" href="${r.profile_url}" target="_blank" rel="noopener">Voir le profil</a>
                    </div>
                </div>`;
            }
            html += '</div>';
        }

        container.innerHTML = html;
    }

    function escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }
});
