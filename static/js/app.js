"use strict";

/* =========================================================
   GUARDIAHEXBOT PLATFORM
   Frontend principal - MASTER + PARTNER + LOGIN
   ========================================================= */

const GH = {
    tokenKey: "guardiahex_access_token",
    roleKey: "guardiahex_role",
    socioKey: "guardiahex_socio_id",
    currentPartnerBotId: null,
    socios: [],
    bots: [],
    commands: [],
};

class ApiError extends Error {
    constructor(message, status = 0, data = null) {
        super(message);
        this.name = "ApiError";
        this.status = status;
        this.data = data;
    }
}

/* =========================================================
   HELPERS
   ========================================================= */

const $ = (selector, parent = document) => parent.querySelector(selector);
const $$ = (selector, parent = document) =>
    Array.from(parent.querySelectorAll(selector));

function getToken() {
    return localStorage.getItem(GH.tokenKey) || "";
}

function getRole() {
    return (
        localStorage.getItem(GH.roleKey) || ""
    ).toUpperCase();
}

function saveSession(data = {}) {
    const token =
        data.access_token ||
        data.token;

    const role =
        data.role ||
        data.user_role;

    const socioId =
        data.socio_id ??
        data.partner_id;

    if (token) {
        localStorage.setItem(
            GH.tokenKey,
            token
        );
    }

    if (role) {
        localStorage.setItem(
            GH.roleKey,
            String(role).toUpperCase()
        );
    }

    if (
        socioId !== undefined &&
        socioId !== null
    ) {
        localStorage.setItem(
            GH.socioKey,
            String(socioId)
        );
    }
}

function clearSession() {
    localStorage.removeItem(
        GH.tokenKey
    );

    localStorage.removeItem(
        GH.roleKey
    );

    localStorage.removeItem(
        GH.socioKey
    );
}

function escapeHtml(value) {
    const node =
        document.createElement("div");

    node.textContent =
        String(value ?? "");

    return node.innerHTML;
}

function formatNumber(value) {
    return new Intl.NumberFormat(
        "es-PE"
    ).format(
        Number(value || 0)
    );
}

function bool(value) {
    return (
        value === true ||
        value === 1 ||
        value === "1" ||
        value === "true"
    );
}

function normalizeUsername(value) {
    if (!value) {
        return "—";
    }

    const text =
        String(value).trim();

    return text.startsWith("@")
        ? text
        : `@${text}`;
}

function setText(id, value) {
    const element =
        document.getElementById(id);

    if (element) {
        element.textContent =
            value ?? "—";
    }
}

function setClassStatus(
    element,
    state
) {
    if (!element) {
        return;
    }

    element.classList.remove(
        "status-online",
        "status-pending",
        "status-error"
    );

    element.classList.add(
        state === "online"
            ? "status-online"
            : state === "error"
                ? "status-error"
                : "status-pending"
    );
}

function statusHtml(
    enabled,
    onlineText = "ONLINE",
    offlineText = "OFFLINE"
) {
    return enabled
        ? `<span class="status-online">${escapeHtml(onlineText)}</span>`
        : `<span class="status-error">${escapeHtml(offlineText)}</span>`;
}

function showAlert(
    element,
    message,
    type = "error"
) {
    if (!element) {
        return;
    }

    element.hidden = false;
    element.textContent =
        message;

    if (type === "success") {
        element.style.color =
            "#b9ffec";

        element.style.background =
            "rgba(0,245,184,.07)";

        element.style.borderColor =
            "rgba(0,245,184,.18)";
    } else {
        element.style.color = "";
        element.style.background = "";
        element.style.borderColor = "";
    }
}

function hideAlert(element) {
    if (!element) {
        return;
    }

    element.hidden = true;
    element.textContent = "";
}

function openModal(element) {
    if (!element) {
        return;
    }

    element.hidden = false;

    document.body.style.overflow =
        "hidden";
}

function closeModal(element) {
    if (!element) {
        return;
    }

    element.hidden = true;

    document.body.style.overflow =
        "";
}

function closeAllModals() {
    $$(".modal").forEach(
        closeModal
    );
}

function firstArray(
    data,
    keys = [
        "items",
        "results",
        "data",
        "bots",
        "socios",
        "commands"
    ]
) {
    if (Array.isArray(data)) {
        return data;
    }

    for (const key of keys) {
        if (
            Array.isArray(
                data?.[key]
            )
        ) {
            return data[key];
        }
    }

    return [];
}

/* =========================================================
   API
   ========================================================= */

async function apiRequest(
    url,
    options = {}
) {
    const headers = {
        Accept:
            "application/json",
        ...(options.headers || {}),
    };

    const token =
        getToken();

    if (token) {
        headers.Authorization =
            `Bearer ${token}`;
    }

    if (
        options.body &&
        !(
            options.body
            instanceof FormData
        )
    ) {
        headers["Content-Type"] =
            headers["Content-Type"] ||
            "application/json";
    }

    let response;

    try {
        response =
            await fetch(
                url,
                {
                    ...options,
                    headers,
                }
            );
    } catch (error) {
        throw new ApiError(
            "No se pudo conectar con el servidor.",
            0,
            error
        );
    }

    const contentType =
        response.headers.get(
            "content-type"
        ) || "";

    let data = null;

    try {
        data =
            contentType.includes(
                "application/json"
            )
                ? await response.json()
                : await response.text();
    } catch {
        data = null;
    }

    if (
        response.status === 401
    ) {
        clearSession();

        if (
            !location.pathname.includes(
                "/login"
            )
        ) {
            location.href =
                "/login";
        }

        throw new ApiError(
            "Sesión expirada.",
            401,
            data
        );
    }

    if (!response.ok) {
        const message =
            (
                data &&
                typeof data ===
                    "object" &&
                (
                    data.detail ||
                    data.message ||
                    data.error
                )
            ) ||
            (
                typeof data ===
                    "string" &&
                data.trim()
            ) ||
            `Error HTTP ${response.status}`;

        throw new ApiError(
            String(message),
            response.status,
            data
        );
    }

    return data;
}

async function apiFirst(
    candidates
) {
    let lastError = null;

    for (
        const candidate
        of candidates
    ) {
        const request =
            typeof candidate ===
            "string"
                ? {
                    url: candidate
                }
                : candidate;

        try {
            return await apiRequest(
                request.url,
                request.options || {}
            );
        } catch (error) {
            lastError = error;

            if (
                !(
                    error
                    instanceof ApiError
                ) ||
                ![
                    404,
                    405
                ].includes(
                    error.status
                )
            ) {
                throw error;
            }
        }
    }

    throw (
        lastError ||
        new ApiError(
            "Ruta API no disponible."
        )
    );
}

/* =========================================================
   LOGIN / SESSION
   ========================================================= */

function initLogin() {
    const form =
        $("#login-form");

    if (!form) {
        return;
    }

    const username =
        $("#username");

    const password =
        $("#password");

    const alert =
        $("#login-alert");

    const button =
        $("#login-button");

    const buttonText =
        $("#login-button-text");

    const toggle =
        $("#toggle-password");

    toggle?.addEventListener(
        "click",
        () => {
            const showing =
                password.type ===
                "text";

            password.type =
                showing
                    ? "password"
                    : "text";

            toggle.textContent =
                showing
                    ? "VER"
                    : "OCULTAR";

            toggle.setAttribute(
                "aria-label",
                showing
                    ? "Mostrar contraseña"
                    : "Ocultar contraseña"
            );
        }
    );

    form.addEventListener(
        "submit",
        async event => {
            event.preventDefault();

            hideAlert(alert);

            button.disabled =
                true;

            if (buttonText) {
                buttonText.textContent =
                    "VERIFICANDO...";
            }

            const payload = {
                username:
                    username.value.trim(),

                password:
                    password.value,
            };

            try {
                const data =
                    await apiFirst([
                        {
                            url:
                                "/api/auth/login",

                            options: {
                                method:
                                    "POST",

                                body:
                                    JSON.stringify(
                                        payload
                                    ),
                            },
                        },

                        {
                            url:
                                "/api/auth/partner/login",

                            options: {
                                method:
                                    "POST",

                                body:
                                    JSON.stringify(
                                        payload
                                    ),
                            },
                        },
                    ]);

                saveSession(
                    data || {}
                );

                const role =
                    String(
                        data?.role ||
                        data?.user_role ||
                        getRole()
                    ).toUpperCase();

                location.href =
                    role ===
                    "SUPERADMIN"
                        ? "/master/dashboard"
                        : "/partner/panel";

            } catch (error) {
                showAlert(
                    alert,
                    error.message ||
                    "Credenciales inválidas."
                );
            } finally {
                button.disabled =
                    false;

                if (buttonText) {
                    buttonText.textContent =
                        "ACCEDER AL SISTEMA";
                }
            }
        }
    );
}

function initLogout() {
    $$("#logout-button")
        .forEach(
            button => {
                button.addEventListener(
                    "click",
                    () => {
                        clearSession();

                        location.href =
                            "/login";
                    }
                );
            }
        );
}

/* =========================================================
   GLOBAL UI
   ========================================================= */

function initSidebar() {
    const sidebar =
        $("#sidebar");

    const toggle =
        $("#menu-toggle");

    if (
        !sidebar ||
        !toggle
    ) {
        return;
    }

    toggle.addEventListener(
        "click",
        () =>
            sidebar.classList
                .toggle("open")
    );

    document.addEventListener(
        "click",
        event => {
            if (
                innerWidth <= 820 &&
                sidebar.classList
                    .contains("open") &&
                !sidebar.contains(
                    event.target
                ) &&
                !toggle.contains(
                    event.target
                )
            ) {
                sidebar.classList
                    .remove("open");
            }
        }
    );
}

function initGenericModals() {
    document.addEventListener(
        "keydown",
        event => {
            if (
                event.key ===
                "Escape"
            ) {
                closeAllModals();
            }
        }
    );

    $$(".modal-backdrop")
        .forEach(
            backdrop => {
                backdrop.addEventListener(
                    "click",
                    () =>
                        closeModal(
                            backdrop.closest(
                                ".modal"
                            )
                        )
                );
            }
        );
}

/* =========================================================
   DASHBOARD MASTER
   ========================================================= */

async function loadMasterDashboard() {
    if (
        !$("#stat-bots-total")
    ) {
        return;
    }

    try {
        const data =
            await apiFirst([
                "/api/dashboard/master",
                "/api/statistics/global",
                "/api/statistics/master",
            ]);

        setText(
            "stat-bots-total",
            formatNumber(
                data.bots_total ??
                data.total_bots
            )
        );

        setText(
            "stat-bots-active",
            formatNumber(
                data.bots_active ??
                data.active_bots
            )
        );

        setText(
            "stat-users-total",
            formatNumber(
                data.users_total ??
                data.total_users
            )
        );

        setText(
            "stat-sellers-total",
            formatNumber(
                data.sellers_total ??
                data.total_sellers
            )
        );

        setText(
            "stat-credits",
            formatNumber(
                data.credits_total ??
                data.credits_in_circulation
            )
        );

        setText(
            "stat-subscriptions",
            formatNumber(
                data.subscriptions_active ??
                data.active_subscriptions
            )
        );

        setText(
            "stat-errors",
            formatNumber(
                data.errors_today ??
                data.today_errors
            )
        );

        renderDashboardBots(
            firstArray(
                data,
                [
                    "bots",
                    "items"
                ]
            )
        );

    } catch (error) {
        console.error(
            "Dashboard:",
            error
        );
    }

    await loadProviderStatus();
}

function renderDashboardBots(
    bots
) {
    const container =
        $("#bots-container");

    if (!container) {
        return;
    }

    if (!bots.length) {
        container.innerHTML = `
            <div class="empty-state">
                <p>
                    No existen bots registrados.
                </p>
            </div>
        `;

        return;
    }

    container.innerHTML =
        bots
            .slice(0, 8)
            .map(
                bot => `
                    <div class="quick-action">

                        <span>
                            ◉
                        </span>

                        <div style="flex:1">

                            <strong>
                                ${escapeHtml(
                                    bot.display_name ||
                                    bot.username ||
                                    `BOT #${bot.id}`
                                )}
                            </strong>

                            <small>
                                ${escapeHtml(
                                    normalizeUsername(
                                        bot.username
                                    )
                                )}
                                •
                                ${escapeHtml(
                                    bot.version ||
                                    "—"
                                )}
                            </small>

                        </div>

                        ${statusHtml(
                            bool(
                                bot.enabled ??
                                bot.is_enabled
                            )
                        )}

                    </div>
                `
            )
            .join("");
}

/* =========================================================
   SOCIOS MASTER
   ========================================================= */

async function loadSocios() {
    const tbody =
        $("#socios-table-body");

    if (!tbody) {
        return;
    }

    try {
        const data =
            await apiFirst([
                "/api/socios",
                "/api/socios/",
            ]);

        GH.socios =
            firstArray(
                data,
                [
                    "items",
                    "socios",
                    "data"
                ]
            );

        renderSocios(
            GH.socios
        );

        const active =
            GH.socios.filter(
                item =>
                    bool(
                        item.active ??
                        item.is_active
                    )
            ).length;

        const bots =
            GH.socios.reduce(
                (
                    sum,
                    item
                ) =>
                    sum +
                    Number(
                        item.bots_count ??
                        item.bot_count ??
                        0
                    ),
                0
            );

        setText(
            "socios-total",
            formatNumber(
                GH.socios.length
            )
        );

        setText(
            "socios-active",
            formatNumber(
                active
            )
        );

        setText(
            "socios-disabled",
            formatNumber(
                GH.socios.length -
                active
            )
        );

        setText(
            "socios-bots",
            formatNumber(
                bots
            )
        );

    } catch (error) {
        tbody.innerHTML = `
            <tr>
                <td
                    colspan="7"
                    class="table-loading"
                >
                    ${escapeHtml(
                        error.message
                    )}
                </td>
            </tr>
        `;
    }
}

function renderSocios(items) {
    const tbody =
        $("#socios-table-body");

    if (!tbody) {
        return;
    }

    if (!items.length) {
        tbody.innerHTML = `
            <tr>
                <td
                    colspan="7"
                    class="table-loading"
                >
                    No hay socios registrados.
                </td>
            </tr>
        `;

        return;
    }

    tbody.innerHTML =
        items.map(
            socio => {
                const active =
                    bool(
                        socio.active ??
                        socio.is_active
                    );

                return `
                    <tr>

                        <td>
                            #${escapeHtml(
                                socio.id
                            )}
                        </td>

                        <td>

                            <strong>
                                ${escapeHtml(
                                    socio.display_name ||
                                    socio.username ||
                                    "—"
                                )}
                            </strong>

                            <br>

                            <small>
                                ${escapeHtml(
                                    socio.username ||
                                    ""
                                )}
                            </small>

                        </td>

                        <td>
                            ${escapeHtml(
                                socio.telegram_id ||
                                "—"
                            )}
                        </td>

                        <td>
                            ${formatNumber(
                                socio.bots_count ??
                                socio.bot_count ??
                                0
                            )}
                        </td>

                        <td>
                            ${statusHtml(
                                active,
                                "ACTIVO",
                                "BLOQUEADO"
                            )}
                        </td>

                        <td>
                            ${
                                bool(
                                    socio.must_change_password
                                )
                                    ? '<span class="status-pending">CAMBIO PENDIENTE</span>'
                                    : '<span class="status-online">OK</span>'
                            }
                        </td>

                        <td>

                            <button
                                class="btn-secondary socio-toggle"
                                data-id="${socio.id}"
                                data-active="${active}"
                            >
                                ${
                                    active
                                        ? "DESACTIVAR"
                                        : "ACTIVAR"
                                }
                            </button>

                        </td>

                    </tr>
                `;
            }
        ).join("");

    $$(".socio-toggle")
        .forEach(
            button => {
                button.addEventListener(
                    "click",
                    () =>
                        toggleSocio(
                            button.dataset.id,
                            button.dataset.active ===
                                "true"
                        )
                );
            }
        );
}

async function toggleSocio(
    id,
    current
) {
    try {
        await apiFirst([
            {
                url:
                    `/api/socios/${id}`,

                options: {
                    method:
                        "PATCH",

                    body:
                        JSON.stringify({
                            active:
                                !current
                        }),
                },
            },

            {
                url:
                    `/api/socios/${id}/${current ? "disable" : "enable"}`,

                options: {
                    method:
                        "POST"
                },
            },
        ]);

        await loadSocios();

    } catch (error) {
        alert(
            error.message
        );
    }
}

function initSocios() {
    if (
        !$("#socios-table-body")
    ) {
        return;
    }

    loadSocios();

    $("#refresh-socios")
        ?.addEventListener(
            "click",
            loadSocios
        );

    $("#socios-search")
        ?.addEventListener(
            "input",
            event => {
                const term =
                    event.target.value
                        .trim()
                        .toLowerCase();

                renderSocios(
                    GH.socios.filter(
                        socio =>
                            String(
                                socio.username ||
                                ""
                            )
                                .toLowerCase()
                                .includes(term) ||

                            String(
                                socio.display_name ||
                                ""
                            )
                                .toLowerCase()
                                .includes(term) ||

                            String(
                                socio.telegram_id ||
                                ""
                            )
                                .includes(term)
                    )
                );
            }
        );

    initCreateSocio();
}

function initCreateSocio() {
    const modal =
        $("#create-socio-modal");

    const form =
        $("#create-socio-form");

    if (
        !modal ||
        !form
    ) {
        return;
    }

    $("#open-create-socio")
        ?.addEventListener(
            "click",
            () =>
                openModal(
                    modal
                )
        );

    $("#close-create-socio")
        ?.addEventListener(
            "click",
            () =>
                closeModal(
                    modal
                )
        );

    $("#cancel-create-socio")
        ?.addEventListener(
            "click",
            () =>
                closeModal(
                    modal
                )
        );

    form.addEventListener(
        "submit",
        async event => {
            event.preventDefault();

            const alertBox =
                $("#socio-form-alert");

            hideAlert(
                alertBox
            );

            const telegramValue =
                $("#socio-telegram")
                    ?.value.trim();

            const passwordValue =
                $("#socio-password")
                    ?.value || "";

            const payload = {
                username:
                    $("#socio-username")
                        .value.trim(),

                display_name:
                    $("#socio-name")
                        .value.trim(),

                telegram_id:
                    telegramValue
                        ? Number(
                            telegramValue
                        )
                        : null,

                email:
                    $("#socio-email")
                        ?.value.trim() ||
                    null,
            };

            if (passwordValue) {
                payload.password =
                    passwordValue;
            }

            try {
                const data =
                    await apiRequest(
                        "/api/socios",
                        {
                            method:
                                "POST",

                            body:
                                JSON.stringify(
                                    payload
                                ),
                        }
                    );

                form.reset();

                closeModal(
                    modal
                );

                showSocioCredentials(
                    data ||
                    payload
                );

                await loadSocios();

            } catch (error) {
                showAlert(
                    alertBox,
                    error.message
                );
            }
        }
    );
}

function showSocioCredentials(
    data
) {
    const modal =
        $("#credentials-modal");

    if (!modal) {
        return;
    }

    setText(
        "credential-username",
        data.username ||
        "—"
    );

    setText(
        "credential-password",
        data.temporary_password ||
        data.generated_password ||
        "Contraseña definida"
    );

    openModal(
        modal
    );

    $("#close-credentials")
        ?.addEventListener(
            "click",
            () =>
                closeModal(
                    modal
                ),
            {
                once: true
            }
        );

    $("#copy-credentials")
        ?.addEventListener(
            "click",
            async () => {
                const user =
                    $("#credential-username")
                        ?.textContent ||
                    "";

                const pass =
                    $("#credential-password")
                        ?.textContent ||
                    "";

                try {
                    await navigator.clipboard
                        .writeText(
                            `Usuario: ${user}\nContraseña: ${pass}`
                        );

                } catch {
                    alert(
                        `Usuario: ${user}\nContraseña: ${pass}`
                    );
                }
            },
            {
                once: true
            }
        );
}

/* =========================================================
   BOTS MASTER
   ========================================================= */

async function loadBots() {
    const container =
        $("#master-bots-container");

    if (!container) {
        return;
    }

    try {
        const data =
            await apiFirst([
                "/api/bots",
                "/api/bots/",
            ]);

        GH.bots =
            firstArray(
                data,
                [
                    "items",
                    "bots",
                    "data"
                ]
            );

        renderBots(
            GH.bots
        );

        updateBotStats();

        populateBotSocios();

    } catch (error) {
        container.innerHTML = `
            <div class="empty-state">
                <p>
                    ${escapeHtml(
                        error.message
                    )}
                </p>
            </div>
        `;
    }
}

function updateBotStats() {
    const online =
        GH.bots.filter(
            bot =>
                bool(
                    bot.enabled ??
                    bot.is_enabled
                ) &&
                !bool(
                    bot.maintenance_mode
                )
        ).length;

    const maintenance =
        GH.bots.filter(
            bot =>
                bool(
                    bot.maintenance_mode
                )
        ).length;

    const offline =
        Math.max(
            0,
            GH.bots.length -
            online -
            maintenance
        );

    setText(
        "bots-total",
        formatNumber(
            GH.bots.length
        )
    );

    setText(
        "bots-online",
        formatNumber(
            online
        )
    );

    setText(
        "bots-offline",
        formatNumber(
            offline
        )
    );

    setText(
        "bots-maintenance",
        formatNumber(
            maintenance
        )
    );
}

function renderBots(items) {
    const container =
        $("#master-bots-container");

    if (!container) {
        return;
    }

    if (!items.length) {
        container.innerHTML = `
            <div class="empty-state">
                <p>
                    No hay bots registrados.
                </p>
            </div>
        `;

        return;
    }

    container.innerHTML =
        items.map(
            bot => {
                const enabled =
                    bool(
                        bot.enabled ??
                        bot.is_enabled
                    );

                return `
                    <article class="panel-card">

                        <div class="panel-card-header">

                            <div>

                                <span class="section-label">
                                    ${escapeHtml(
                                        bot.version ||
                                        "—"
                                    )}
                                </span>

                                <h4>
                                    ${escapeHtml(
                                        bot.display_name ||
                                        bot.username ||
                                        `BOT #${bot.id}`
                                    )}
                                </h4>

                            </div>

                            ${statusHtml(
                                enabled
                            )}

                        </div>

                        <div class="status-row">

                            <span>
                                USERNAME
                            </span>

                            <strong>
                                ${escapeHtml(
                                    normalizeUsername(
                                        bot.username
                                    )
                                )}
                            </strong>

                        </div>

                        <div class="status-row">

                            <span>
                                SOCIO
                            </span>

                            <strong>
                                ${escapeHtml(
                                    bot.socio_name ||
                                    bot.socio_id ||
                                    "MASTER"
                                )}
                            </strong>

                        </div>

                        <div class="status-row">

                            <span>
                                LÍMITE DIARIO
                            </span>

                            <strong>
                                ${formatNumber(
                                    bot.daily_query_limit ||
                                    0
                                )}
                            </strong>

                        </div>

                        <div class="status-row">

                            <span>
                                MANTENIMIENTO
                            </span>

                            <strong>
                                ${
                                    bool(
                                        bot.maintenance_mode
                                    )
                                        ? '<span class="status-pending">ACTIVO</span>'
                                        : '<span class="status-online">NO</span>'
                                }
                            </strong>

                        </div>

                        <div
                            style="
                                display:flex;
                                gap:8px;
                                margin-top:15px;
                                flex-wrap:wrap
                            "
                        >

                            <button
                                class="btn-secondary bot-toggle"
                                data-id="${bot.id}"
                                data-enabled="${enabled}"
                                style="flex:1"
                            >
                                ${
                                    enabled
                                        ? "APAGAR"
                                        : "ENCENDER"
                                }
                            </button>

                            <button
                                class="btn-secondary bot-settings-open"
                                data-id="${bot.id}"
                                style="flex:1"
                            >
                                CONFIGURAR
                            </button>

                        </div>

                    </article>
                `;
            }
        ).join("");

    $$(".bot-toggle")
        .forEach(
            button => {
                button.addEventListener(
                    "click",
                    async () => {
                        const id =
                            button.dataset.id;

                        const enabled =
                            button.dataset
                                .enabled ===
                            "true";

                        try {
                            await apiFirst([
                                {
                                    url:
                                        `/api/bots/${id}/${enabled ? "disable" : "enable"}`,

                                    options: {
                                        method:
                                            "POST"
                                    },
                                },

                                {
                                    url:
                                        `/api/bots/${id}`,

                                    options: {
                                        method:
                                            "PATCH",

                                        body:
                                            JSON.stringify({
                                                enabled:
                                                    !enabled
                                            }),
                                    },
                                },
                            ]);

                            await loadBots();

                        } catch (error) {
                            alert(
                                error.message
                            );
                        }
                    }
                );
            }
        );

    $$(".bot-settings-open")
        .forEach(
            button => {
                button.addEventListener(
                    "click",
                    () =>
                        openBotSettings(
                            button.dataset.id
                        )
                );
            }
        );
}

function populateBotSocios() {
    const select =
        $("#bot-socio");

    if (!select) {
        return;
    }

    const fill =
        socios => {
            select.innerHTML =
                `
                    <option value="">
                        Seleccionar socio
                    </option>
                ` +
                socios.map(
                    socio => `
                        <option
                            value="${socio.id}"
                        >
                            ${escapeHtml(
                                socio.display_name ||
                                socio.username ||
                                `Socio #${socio.id}`
                            )}
                        </option>
                    `
                ).join("");
        };

    if (
        GH.socios.length
    ) {
        fill(
            GH.socios
        );

        return;
    }

    apiFirst([
        "/api/socios",
        "/api/socios/"
    ])
        .then(
            data => {
                GH.socios =
                    firstArray(
                        data,
                        [
                            "items",
                            "socios",
                            "data"
                        ]
                    );

                fill(
                    GH.socios
                );
            }
        )
        .catch(
            console.error
        );
}

function initBots() {
    if (
        !$("#master-bots-container")
    ) {
        return;
    }

    loadBots();

    $("#refresh-bots")
        ?.addEventListener(
            "click",
            loadBots
        );

    const search =
        $("#bots-search");

    const version =
        $("#bots-version-filter");

    const status =
        $("#bots-status-filter");

    const filter = () => {
        const term =
            (
                search?.value ||
                ""
            )
                .trim()
                .toLowerCase();

        const versionValue =
            version?.value ||
            "";

        const statusValue =
            status?.value ||
            "";

        renderBots(
            GH.bots.filter(
                bot => {
                    const enabled =
                        bool(
                            bot.enabled ??
                            bot.is_enabled
                        );

                    const maintenance =
                        bool(
                            bot.maintenance_mode
                        );

                    const textMatch =
                        !term ||
                        [
                            bot.display_name,
                            bot.username,
                            bot.socio_name,
                            bot.id
                        ]
                            .some(
                                value =>
                                    String(
                                        value ||
                                        ""
                                    )
                                        .toLowerCase()
                                        .includes(
                                            term
                                        )
                            );

                    const versionMatch =
                        !versionValue ||
                        String(
                            bot.version ||
                            ""
                        ).toUpperCase() ===
                        versionValue;

                    const statusMatch =
                        !statusValue ||

                        (
                            statusValue ===
                            "ONLINE" &&
                            enabled &&
                            !maintenance
                        ) ||

                        (
                            statusValue ===
                            "OFFLINE" &&
                            !enabled
                        ) ||

                        (
                            statusValue ===
                            "MAINTENANCE" &&
                            maintenance
                        );

                    return (
                        textMatch &&
                        versionMatch &&
                        statusMatch
                    );
                }
            )
        );
    };

    search?.addEventListener(
        "input",
        filter
    );

    version?.addEventListener(
        "change",
        filter
    );

    status?.addEventListener(
        "change",
        filter
    );

    initCreateBot();

    initBotSettings();
}

function initCreateBot() {
    const modal =
        $("#create-bot-modal");

    const form =
        $("#create-bot-form");

    if (
        !modal ||
        !form
    ) {
        return;
    }

    $("#open-create-bot")
        ?.addEventListener(
            "click",
            () =>
                openModal(
                    modal
                )
        );

    $("#close-create-bot")
        ?.addEventListener(
            "click",
            () =>
                closeModal(
                    modal
                )
        );

    $("#cancel-create-bot")
        ?.addEventListener(
            "click",
            () =>
                closeModal(
                    modal
                )
        );

    form.addEventListener(
        "submit",
        async event => {
            event.preventDefault();

            const alertBox =
                $("#bot-form-alert");

            hideAlert(
                alertBox
            );

            const socioId =
                $("#bot-socio")
                    ?.value;

            const payload = {
                socio_id:
                    socioId
                        ? Number(
                            socioId
                        )
                        : null,

                display_name:
                    $("#bot-display-name")
                        .value.trim(),

                username:
                    $("#bot-username")
                        ?.value
                        .trim()
                        .replace(
                            /^@/,
                            ""
                        ) ||
                    null,

                administration_name:
                    $("#bot-administration")
                        ?.value.trim() ||
                    null,

                version:
                    $("#bot-version")
                        .value,

                daily_query_limit:
                    Number(
                        $("#bot-daily-limit")
                            .value
                    ),

                is_master:
                    $("#bot-is-master")
                        ?.checked ||
                    false,
            };

            try {
                await apiRequest(
                    "/api/bots",
                    {
                        method:
                            "POST",

                        body:
                            JSON.stringify(
                                payload
                            ),
                    }
                );

                form.reset();

                closeModal(
                    modal
                );

                await loadBots();

            } catch (error) {
                showAlert(
                    alertBox,
                    error.message
                );
            }
        }
    );
}

function initBotSettings() {
    const modal =
        $("#bot-settings-modal");

    const form =
        $("#bot-settings-form");

    if (
        !modal ||
        !form
    ) {
        return;
    }

    $("#close-bot-settings")
        ?.addEventListener(
            "click",
            () =>
                closeModal(
                    modal
                )
        );

    $("#cancel-bot-settings")
        ?.addEventListener(
            "click",
            () =>
                closeModal(
                    modal
                )
        );

    form.addEventListener(
        "submit",
        async event => {
            event.preventDefault();

            const id =
                $("#settings-bot-id")
                    .value;

            if (!id) {
                return;
            }

            const payload = {
                display_name:
                    $("#settings-display-name")
                        ?.value.trim() ||
                    null,

                username:
                    $("#settings-username")
                        ?.value
                        .trim()
                        .replace(
                            /^@/,
                            ""
                        ) ||
                    null,

                administration_name:
                    $("#settings-administration")
                        ?.value.trim() ||
                    null,

                daily_query_limit:
                    Number(
                        $("#settings-limit")
                            ?.value ||
                        0
                    ) ||
                    null,

                channel_url:
                    $("#settings-channel")
                        ?.value.trim() ||
                    null,

                group_url:
                    $("#settings-group")
                        ?.value.trim() ||
                    null,

                history_chat_id:
                    $("#settings-history")
                        ?.value
                        ? Number(
                            $("#settings-history")
                                .value
                        )
                        : null,

                sales_chat_id:
                    $("#settings-sales")
                        ?.value
                        ? Number(
                            $("#settings-sales")
                                .value
                        )
                        : null,

                maintenance_mode:
                    $("#settings-maintenance")
                        ?.checked ||
                    false,

                maintenance_message:
                    $("#settings-maintenance-message")
                        ?.value.trim() ||
                    null,
            };

            try {
                await apiRequest(
                    `/api/bots/${id}`,
                    {
                        method:
                            "PATCH",

                        body:
                            JSON.stringify(
                                payload
                            ),
                    }
                );

                closeModal(
                    modal
                );

                await loadBots();

            } catch (error) {
                alert(
                    error.message
                );
            }
        }
    );
}

function openBotSettings(id) {
    const modal =
        $("#bot-settings-modal");

    const bot =
        GH.bots.find(
            item =>
                String(
                    item.id
                ) ===
                String(
                    id
                )
        );

    if (
        !modal ||
        !bot
    ) {
        return;
    }

    setText(
        "settings-bot-title",
        `Configurar ${
            bot.display_name ||
            bot.username ||
            `BOT #${bot.id}`
        }`
    );

    $("#settings-bot-id")
        .value =
        bot.id;

    $("#settings-display-name")
        .value =
        bot.display_name ||
        "";

    $("#settings-username")
        .value =
        bot.username ||
        "";

    $("#settings-administration")
        .value =
        bot.administration_name ||
        "";

    $("#settings-limit")
        .value =
        bot.daily_query_limit ||
        1000;

    $("#settings-channel")
        .value =
        bot.channel_url ||
        bot.channel ||
        "";

    $("#settings-group")
        .value =
        bot.group_url ||
        bot.group ||
        "";

    $("#settings-history")
        .value =
        bot.history_chat_id ||
        "";

    $("#settings-sales")
        .value =
        bot.sales_chat_id ||
        "";

    $("#settings-maintenance")
        .checked =
        bool(
            bot.maintenance_mode
        );

    $("#settings-maintenance-message")
        .value =
        bot.maintenance_message ||
        "";

    openModal(
        modal
    );
}

/* =========================================================
   VERSIONES
   ========================================================= */

const VERSION_INFO = {
    V1: {
        name:
            "V1 INICIAL",

        categories:
            "10/19",

        commands:
            "25/72",

        limit:
            1000,
    },

    V2: {
        name:
            "V2 INICIAL PLUS",

        categories:
            "13/19",

        commands:
            "40/72",

        limit:
            2000,
    },

    V3: {
        name:
            "V3 AVANZADO",

        categories:
            "16/19",

        commands:
            "55/72",

        limit:
            5000,
    },

    V4: {
        name:
            "V4 AVANZADO PLUS",

        categories:
            "18/19",

        commands:
            "65/72",

        limit:
            9000,
    },

    V5: {
        name:
            "V5 BUSINESS",

        categories:
            "19/19",

        commands:
            "72/72",

        limit:
            10000,
    },
};

async function loadVersionsBots() {
    const tbody =
        $("#versions-bots-table");

    if (!tbody) {
        return;
    }

    try {
        const data =
            await apiFirst([
                "/api/bots",
                "/api/bots/",
            ]);

        const bots =
            firstArray(
                data,
                [
                    "items",
                    "bots",
                    "data"
                ]
            );

        GH.bots =
            bots;

        tbody.innerHTML =
            bots.length
                ? bots.map(
                    bot => {
                        const version =
                            String(
                                bot.version ||
                                "V1"
                            ).toUpperCase();

                        const info =
                            VERSION_INFO[
                                version
                            ] ||
                            VERSION_INFO.V1;

                        return `
                            <tr>

                                <td>
                                    ${escapeHtml(
                                        bot.display_name ||
                                        bot.username ||
                                        `BOT #${bot.id}`
                                    )}
                                </td>

                                <td>
                                    ${escapeHtml(
                                        bot.socio_name ||
                                        bot.socio_id ||
                                        "MASTER"
                                    )}
                                </td>

                                <td>
                                    <strong>
                                        ${escapeHtml(
                                            version
                                        )}
                                    </strong>
                                </td>

                                <td>
                                    ${escapeHtml(
                                        info.categories
                                    )}
                                </td>

                                <td>
                                    ${escapeHtml(
                                        info.commands
                                    )}
                                </td>

                                <td>
                                    ${formatNumber(
                                        bot.daily_query_limit ||
                                        info.limit
                                    )}
                                </td>

                                <td>

                                    <button
                                        class="btn-secondary change-version"
                                        data-id="${bot.id}"
                                        data-name="${escapeHtml(
                                            bot.display_name ||
                                            bot.username ||
                                            "BOT"
                                        )}"
                                        data-version="${escapeHtml(
                                            version
                                        )}"
                                    >
                                        CAMBIAR
                                    </button>

                                </td>

                            </tr>
                        `;
                    }
                ).join("")
                : `
                    <tr>
                        <td
                            colspan="7"
                            class="table-loading"
                        >
                            No hay bots.
                        </td>
                    </tr>
                `;

        initVersionButtons();

    } catch (error) {
        tbody.innerHTML = `
            <tr>
                <td
                    colspan="7"
                    class="table-loading"
                >
                    ${escapeHtml(
                        error.message
                    )}
                </td>
            </tr>
        `;
    }
}

function initVersionButtons() {
    const modal =
        $("#change-version-modal");

    $$(".change-version")
        .forEach(
            button => {
                button.addEventListener(
                    "click",
                    () => {
                        $("#change-version-bot-id")
                            .value =
                            button.dataset.id;

                        setText(
                            "change-version-bot-name",
                            button.dataset.name
                        );

                        $("#change-version-select")
                            .value =
                            button.dataset
                                .version ||
                            "V1";

                        updateVersionPreview();

                        openModal(
                            modal
                        );
                    }
                );
            }
        );
}

function updateVersionPreview() {
    const select =
        $("#change-version-select");

    const preview =
        $("#version-change-preview");

    if (
        !select ||
        !preview
    ) {
        return;
    }

    const info =
        VERSION_INFO[
            select.value
        ] ||
        VERSION_INFO.V1;

    preview.textContent =
        `${info.name} • ` +
        `${info.categories} categorías • ` +
        `${info.commands} CMD • ` +
        `${formatNumber(info.limit)} consultas/día`;
}

function initVersions() {
    if (
        !$("#versions-bots-table")
    ) {
        return;
    }

    loadVersionsBots();

    $("#refresh-versions")
        ?.addEventListener(
            "click",
            loadVersionsBots
        );

    $("#change-version-select")
        ?.addEventListener(
            "change",
            updateVersionPreview
        );

    const modal =
        $("#change-version-modal");

    $("#close-change-version")
        ?.addEventListener(
            "click",
            () =>
                closeModal(
                    modal
                )
        );

    $("#cancel-change-version")
        ?.addEventListener(
            "click",
            () =>
                closeModal(
                    modal
                )
        );

    $("#change-version-form")
        ?.addEventListener(
            "submit",
            async event => {
                event.preventDefault();

                const id =
                    $("#change-version-bot-id")
                        .value;

                const version =
                    $("#change-version-select")
                        .value;

                const info =
                    VERSION_INFO[
                        version
                    ];

                try {
                    await apiFirst([
                        {
                            url:
                                `/api/versions/bots/${id}`,

                            options: {
                                method:
                                    "PATCH",

                                body:
                                    JSON.stringify({
                                        version
                                    }),
                            },
                        },

                        {
                            url:
                                `/api/bots/${id}/version`,

                            options: {
                                method:
                                    "PATCH",

                                body:
                                    JSON.stringify({
                                        version
                                    }),
                            },
                        },

                        {
                            url:
                                `/api/bots/${id}`,

                            options: {
                                method:
                                    "PATCH",

                                body:
                                    JSON.stringify({
                                        version,

                                        daily_query_limit:
                                            info?.limit,
                                    }),
                            },
                        },
                    ]);

                    closeModal(
                        modal
                    );

                    await loadVersionsBots();

                } catch (error) {
                    alert(
                        error.message
                    );
                }
            }
        );

    initVersionDetails();
}

function initVersionDetails() {
    const modal =
        $("#version-details-modal");

    $$(".version-details")
        .forEach(
            button => {
                button.addEventListener(
                    "click",
                    () => {
                        const version =
                            button.dataset
                                .version ||
                            "V1";

                        const info =
                            VERSION_INFO[
                                version
                            ] ||
                            VERSION_INFO.V1;

                        setText(
                            "version-details-title",
                            info.name
                        );

                        const content =
                            $("#version-details-content");

                        if (content) {
                            content.innerHTML = `
                                <div class="status-row">

                                    <span>
                                        CATEGORÍAS
                                    </span>

                                    <strong>
                                        ${escapeHtml(
                                            info.categories
                                        )}
                                    </strong>

                                </div>

                                <div class="status-row">

                                    <span>
                                        COMANDOS
                                    </span>

                                    <strong>
                                        ${escapeHtml(
                                            info.commands
                                        )}
                                    </strong>

                                </div>

                                <div class="status-row">

                                    <span>
                                        LÍMITE DIARIO
                                    </span>

                                    <strong>
                                        ${formatNumber(
                                            info.limit
                                        )}
                                    </strong>

                                </div>
                            `;
                        }

                        openModal(
                            modal
                        );
                    }
                );
            }
        );

    $("#close-version-details")
        ?.addEventListener(
            "click",
            () =>
                closeModal(
                    modal
                )
        );
}

/* =========================================================
   COMANDOS MASTER
   ========================================================= */

async function loadCommands() {
    const tbody =
        $("#commands-table-body");

    if (!tbody) {
        return;
    }

    try {
        const data =
            await apiFirst([
                "/api/commands",
                "/api/commands/",
            ]);

        GH.commands =
            firstArray(
                data,
                [
                    "items",
                    "commands",
                    "data"
                ]
            );

        renderCommands(
            GH.commands
        );

        const enabled =
            GH.commands.filter(
                item =>
                    item.enabled_global !==
                        false &&
                    item.enabled !==
                        false
            ).length;

        const categories =
            new Set(
                GH.commands
                    .map(
                        item =>
                            item.category
                    )
                    .filter(
                        Boolean
                    )
            );

        setText(
            "commands-total",
            formatNumber(
                GH.commands.length
            )
        );

        setText(
            "commands-enabled",
            formatNumber(
                enabled
            )
        );

        setText(
            "commands-disabled",
            formatNumber(
                GH.commands.length -
                enabled
            )
        );

        setText(
            "commands-categories",
            formatNumber(
                categories.size ||
                19
            )
        );

    } catch (error) {
        tbody.innerHTML = `
            <tr>
                <td
                    colspan="8"
                    class="table-loading"
                >
                    ${escapeHtml(
                        error.message
                    )}
                </td>
            </tr>
        `;
    }
}

function renderCommands(items) {
    const tbody =
        $("#commands-table-body");

    if (!tbody) {
        return;
    }

    if (!items.length) {
        tbody.innerHTML = `
            <tr>
                <td
                    colspan="8"
                    class="table-loading"
                >
                    No hay comandos registrados.
                </td>
            </tr>
        `;

        return;
    }

    tbody.innerHTML =
        items.map(
            command => {
                const enabled =
                    command.enabled_global !==
                        false &&
                    command.enabled !==
                        false;

                const versions =
                    Array.isArray(
                        command.available_versions
                    )
                        ? command
                            .available_versions
                            .join(", ")
                        : command
                            .available_versions ||
                        "—";

                return `
                    <tr>

                        <td>
                            <strong>
                                ${escapeHtml(
                                    command.command ||
                                    command.name ||
                                    command.code ||
                                    "—"
                                )}
                            </strong>
                        </td>

                        <td>
                            ${escapeHtml(
                                command.title ||
                                command.description ||
                                "—"
                            )}
                        </td>

                        <td>
                            ${escapeHtml(
                                command.category ||
                                "—"
                            )}
                        </td>

                        <td>
                            ${escapeHtml(
                                command.level ||
                                "—"
                            )}
                        </td>

                        <td>
                            ${formatNumber(
                                command.price ??
                                command.credit_cost ??
                                command.cost ??
                                0
                            )}
                        </td>

                        <td>
                            ${escapeHtml(
                                versions
                            )}
                        </td>

                        <td>
                            ${statusHtml(
                                enabled,
                                "OPERATIVO",
                                "DESACTIVADO"
                            )}
                        </td>

                        <td>

                            <button
                                class="btn-secondary command-toggle"
                                data-id="${command.id}"
                                data-enabled="${enabled}"
                            >
                                ${
                                    enabled
                                        ? "DESACTIVAR"
                                        : "ACTIVAR"
                                }
                            </button>

                        </td>

                    </tr>
                `;
            }
        ).join("");

    $$(".command-toggle")
        .forEach(
            button => {
                button.addEventListener(
                    "click",
                    async () => {
                        const id =
                            button.dataset.id;

                        const enabled =
                            button.dataset
                                .enabled ===
                            "true";

                        try {
                            await apiRequest(
                                `/api/commands/${id}`,
                                {
                                    method:
                                        "PATCH",

                                    body:
                                        JSON.stringify({
                                            enabled_global:
                                                !enabled
                                        }),
                                }
                            );

                            await loadCommands();

                        } catch (error) {
                            alert(
                                error.message
                            );
                        }
                    }
                );
            }
        );
}

function initCommands() {
    if (
        !$("#commands-table-body")
    ) {
        return;
    }

    loadCommands();

    loadCommandBots();

    $("#refresh-commands")
        ?.addEventListener(
            "click",
            loadCommands
        );

    const search =
        $("#commands-search");

    const category =
        $("#commands-category-filter");

    const status =
        $("#commands-status-filter");

    const filter = () => {
        const term =
            (
                search?.value ||
                ""
            )
                .trim()
                .toLowerCase();

        const categoryValue =
            (
                category?.value ||
                ""
            ).toUpperCase();

        const statusValue =
            status?.value ||
            "";

        renderCommands(
            GH.commands.filter(
                command => {
                    const enabled =
                        command.enabled_global !==
                            false &&
                        command.enabled !==
                            false;

                    const textMatch =
                        !term ||
                        [
                            command.command,
                            command.title,
                            command.category,
                            command.description
                        ]
                            .some(
                                value =>
                                    String(
                                        value ||
                                        ""
                                    )
                                        .toLowerCase()
                                        .includes(
                                            term
                                        )
                            );

                    const categoryMatch =
                        !categoryValue ||
                        String(
                            command.category ||
                            ""
                        ).toUpperCase() ===
                        categoryValue;

                    const statusMatch =
                        !statusValue ||

                        (
                            statusValue ===
                            "enabled" &&
                            enabled
                        ) ||

                        (
                            statusValue ===
                            "disabled" &&
                            !enabled
                        );

                    return (
                        textMatch &&
                        categoryMatch &&
                        statusMatch
                    );
                }
            )
        );
    };

    search?.addEventListener(
        "input",
        filter
    );

    category?.addEventListener(
        "change",
        filter
    );

    status?.addEventListener(
        "change",
        filter
    );

    initCreateCommand();
}

async function loadCommandBots() {
    const select =
        $("#command-bot-select");

    if (!select) {
        return;
    }

    try {
        const data =
            await apiFirst([
                "/api/bots",
                "/api/bots/",
            ]);

        const bots =
            firstArray(
                data,
                [
                    "items",
                    "bots",
                    "data"
                ]
            );

        select.innerHTML =
            `
                <option value="">
                    Seleccionar bot
                </option>
            ` +
            bots.map(
                bot => `
                    <option
                        value="${bot.id}"
                    >
                        ${escapeHtml(
                            bot.display_name ||
                            bot.username ||
                            `BOT #${bot.id}`
                        )}
                    </option>
                `
            ).join("");

        select.addEventListener(
            "change",
            () =>
                loadBotCommandOverrides(
                    select.value
                )
        );

    } catch (error) {
        console.error(
            error
        );
    }
}

async function loadBotCommandOverrides(
    botId
) {
    const container =
        $("#bot-command-overrides");

    if (!container) {
        return;
    }

    if (!botId) {
        container.innerHTML = `
            <div class="empty-state">
                <p>
                    Selecciona un bot para ver
                    sus configuraciones particulares.
                </p>
            </div>
        `;

        return;
    }

    container.innerHTML = `
        <div class="empty-state">

            <span class="loader"></span>

            <p>
                Cargando...
            </p>

        </div>
    `;

    try {
        const data =
            await apiFirst([
                `/api/commands/bot/${botId}`,
                `/api/commands/bots/${botId}`,
                `/api/bots/${botId}/commands`,
            ]);

        const items =
            firstArray(
                data,
                [
                    "items",
                    "commands",
                    "overrides",
                    "data"
                ]
            );

        container.innerHTML =
            items.length
                ? items.map(
                    item => `
                        <div class="status-row">

                            <span>
                                ${escapeHtml(
                                    item.command ||
                                    item.command_name ||
                                    item.code ||
                                    `CMD #${item.command_id || item.id}`
                                )}
                            </span>

                            <strong>
                                ${statusHtml(
                                    item.enabled !==
                                        false &&
                                    item.enabled_override !==
                                        false,
                                    "ACTIVO",
                                    "BLOQUEADO"
                                )}
                            </strong>

                        </div>
                    `
                ).join("")
                : `
                    <div class="empty-state">
                        <p>
                            Este bot usa la configuración
                            de su versión sin overrides.
                        </p>
                    </div>
                `;

    } catch (error) {
        if (
            error
            instanceof ApiError &&
            [
                404,
                405
            ].includes(
                error.status
            )
        ) {
            container.innerHTML = `
                <div class="empty-state">
                    <p>
                        Sin overrides configurados.
                    </p>
                </div>
            `;
        } else {
            container.innerHTML = `
                <div class="empty-state">
                    <p>
                        ${escapeHtml(
                            error.message
                        )}
                    </p>
                </div>
            `;
        }
    }
}

function initCreateCommand() {
    const modal =
        $("#create-command-modal");

    const form =
        $("#create-command-form");

    if (
        !modal ||
        !form
    ) {
        return;
    }

    $("#open-create-command")
        ?.addEventListener(
            "click",
            () =>
                openModal(
                    modal
                )
        );

    $("#close-create-command")
        ?.addEventListener(
            "click",
            () =>
                closeModal(
                    modal
                )
        );

    $("#cancel-create-command")
        ?.addEventListener(
            "click",
            () =>
                closeModal(
                    modal
                )
        );

    form.addEventListener(
        "submit",
        async event => {
            event.preventDefault();

            const alertBox =
                $("#command-form-alert");

            hideAlert(
                alertBox
            );

            const versions =
                $$(
                    'input[name="available_versions"]:checked'
                ).map(
                    input =>
                        input.value
                );

            const resultType =
                $("#cmd-result-type")
                    .value;

            const payload = {
                code:
                    $("#cmd-code")
                        .value.trim(),

                command:
                    $("#cmd-command")
                        .value.trim(),

                title:
                    $("#cmd-title")
                        .value.trim(),

                category:
                    $("#cmd-category")
                        .value.trim(),

                level:
                    $("#cmd-level")
                        .value.trim(),

                price:
                    Number(
                        $("#cmd-price")
                            .value
                    ),

                credit_cost:
                    Number(
                        $("#cmd-price")
                            .value
                    ),

                result_type:
                    resultType,

                output_formats:
                    [
                        resultType
                    ],

                provider_key:
                    $("#cmd-provider-key")
                        ?.value.trim() ||
                    null,

                description:
                    $("#cmd-description")
                        ?.value.trim() ||
                    null,

                result_description:
                    $("#cmd-result-description")
                        ?.value.trim() ||
                    null,

                available_versions:
                    versions,

                enabled_global:
                    $("#cmd-enabled")
                        ?.checked ??
                    true,

                charge_on_no_results:
                    $("#cmd-charge-no-results")
                        ?.checked ??
                    true,
            };

            try {
                await apiRequest(
                    "/api/commands",
                    {
                        method:
                            "POST",

                        body:
                            JSON.stringify(
                                payload
                            ),
                    }
                );

                form.reset();

                closeModal(
                    modal
                );

                await loadCommands();

            } catch (error) {
                showAlert(
                    alertBox,
                    error.message
                );
            }
        }
    );
}

/* =========================================================
   PROVIDER / API CENTRAL
   ========================================================= */

async function loadProviderStatus() {
    const marker =
        $("#provider-main-status") ||
        $("#provider-status");

    if (!marker) {
        return;
    }

    try {
        const data =
            await apiFirst([
                "/api/provider",
                "/api/provider/info",
                "/api/provider/status",
            ]);

        const enabled =
            bool(
                data.enabled ??
                data.is_enabled
            );

        const tokenConfigured =
            bool(
                data.token_configured ??
                data.has_token
            );

        const baseUrl =
            data.base_url ||
            data.url ||
            "";

        const timeout =
            data.timeout ||
            data.timeout_seconds ||
            30;

        const ready =
            bool(
                data.ready ??
                data.api_ready ??
                (
                    enabled &&
                    tokenConfigured &&
                    baseUrl
                )
            );

        setText(
            "provider-main-status",
            ready
                ? "OPERATIVA"
                : enabled
                    ? "CONFIGURANDO"
                    : "DESACTIVADA"
        );

        setText(
            "provider-status",
            ready
                ? "OPERATIVA"
                : enabled
                    ? "CONFIGURANDO"
                    : "DESACTIVADA"
        );

        setText(
            "provider-enabled-badge",
            enabled
                ? "ACTIVA"
                : "OFF"
        );

        setText(
            "provider-token-status",
            tokenConfigured
                ? "CONFIGURADO"
                : "NO CONFIGURADO"
        );

        setText(
            "provider-url-status",
            baseUrl ||
            "NO CONFIGURADA"
        );

        setText(
            "provider-timeout-status",
            timeout
        );

        setText(
            "provider-token",
            tokenConfigured
                ? "CONFIGURADO"
                : "NO CONFIGURADO"
        );

        setText(
            "provider-url",
            baseUrl ||
            "—"
        );

        setText(
            "provider-ready",
            ready
                ? "LISTA"
                : "NO LISTA"
        );

        setText(
            "provider-secret-state",
            tokenConfigured
                ? "CONFIGURADO"
                : "PENDIENTE"
        );

        setText(
            "internal-provider-enabled",
            enabled
                ? "SÍ"
                : "NO"
        );

        setText(
            "internal-provider-url",
            baseUrl
                ? "SÍ"
                : "NO"
        );

        setText(
            "internal-provider-token",
            tokenConfigured
                ? "SÍ"
                : "NO"
        );

        setText(
            "internal-provider-ready",
            ready
                ? "SÍ"
                : "NO"
        );

        setClassStatus(
            $("#internal-provider-enabled"),
            enabled
                ? "online"
                : "error"
        );

        setClassStatus(
            $("#internal-provider-url"),
            baseUrl
                ? "online"
                : "pending"
        );

        setClassStatus(
            $("#internal-provider-token"),
            tokenConfigured
                ? "online"
                : "pending"
        );

        setClassStatus(
            $("#internal-provider-ready"),
            ready
                ? "online"
                : "pending"
        );

        const enabledInput =
            $("#provider-enabled");

        const urlInput =
            $("#provider-base-url");

        const timeoutInput =
            $("#provider-timeout");

        if (enabledInput) {
            enabledInput.checked =
                enabled;
        }

        if (urlInput) {
            urlInput.value =
                baseUrl;
        }

        if (timeoutInput) {
            timeoutInput.value =
                timeout;
        }

    } catch (error) {
        console.error(
            "Provider:",
            error
        );

        setText(
            "provider-main-status",
            "NO DISPONIBLE"
        );

        setText(
            "provider-status",
            "NO DISPONIBLE"
        );
    }
}

function initProvider() {
    if (
        !$("#provider-config-form") &&
        !$("#provider-main-status")
    ) {
        return;
    }

    loadProviderStatus();

    $("#refresh-provider")
        ?.addEventListener(
            "click",
            loadProviderStatus
        );

    $("#provider-config-form")
        ?.addEventListener(
            "submit",
            async event => {
                event.preventDefault();

                const alertBox =
                    $("#provider-form-alert");

                hideAlert(
                    alertBox
                );

                const payload = {
                    enabled:
                        $("#provider-enabled")
                            ?.checked ||
                        false,

                    base_url:
                        $("#provider-base-url")
                            ?.value.trim() ||
                        "",

                    timeout:
                        Number(
                            $("#provider-timeout")
                                ?.value ||
                            30
                        ),
                };

                try {
                    await apiFirst([
                        {
                            url:
                                "/api/provider",

                            options: {
                                method:
                                    "PATCH",

                                body:
                                    JSON.stringify(
                                        payload
                                    ),
                            },
                        },

                        {
                            url:
                                "/api/provider/config",

                            options: {
                                method:
                                    "PUT",

                                body:
                                    JSON.stringify(
                                        payload
                                    ),
                            },
                        },
                    ]);

                    showAlert(
                        alertBox,
                        "Configuración guardada.",
                        "success"
                    );

                    await loadProviderStatus();

                } catch (error) {
                    showAlert(
                        alertBox,
                        error.message
                    );
                }
            }
        );

    $("#test-provider")
        ?.addEventListener(
            "click",
            testProviderConnection
        );
}

async function testProviderConnection() {
    const button =
        $("#test-provider");

    if (button) {
        button.disabled =
            true;

        button.textContent =
            "PROBANDO...";
    }

    setText(
        "provider-connection-title",
        "COMPROBANDO"
    );

    setText(
        "provider-connection-message",
        "Validando conectividad con el proveedor..."
    );

    setText(
        "provider-http-code",
        "—"
    );

    setText(
        "provider-latency",
        "—"
    );

    try {
        const started =
            performance.now();

        const data =
            await apiFirst([
                {
                    url:
                        "/api/provider/test",

                    options: {
                        method:
                            "POST"
                    },
                },

                "/api/provider/test",
            ]);

        const elapsed =
            Math.round(
                performance.now() -
                started
            );

        const ok =
            data?.ok !==
                false &&
            data?.success !==
                false;

        setText(
            "provider-connection-title",
            ok
                ? "CONEXIÓN CORRECTA"
                : "SIN CONEXIÓN"
        );

        setText(
            "provider-connection-message",
            data?.message ||
            (
                ok
                    ? "El proveedor respondió correctamente."
                    : "No se pudo validar la conexión."
            )
        );

        setText(
            "provider-http-code",
            data?.status_code ||
            data?.http_status ||
            (
                ok
                    ? "200"
                    : "—"
            )
        );

        setText(
            "provider-latency",
            `${
                data?.latency_ms ??
                elapsed
            } ms`
        );

    } catch (error) {
        setText(
            "provider-connection-title",
            "ERROR DE CONEXIÓN"
        );

        setText(
            "provider-connection-message",
            error.message
        );

    } finally {
        if (button) {
            button.disabled =
                false;

            button.textContent =
                "⚡ PROBAR CONEXIÓN";
        }
    }
}

/* =========================================================
   PARTNER PANEL
   ========================================================= */

async function initPartnerPanel() {
    if (
        !$("#partner-bot-select")
    ) {
        return;
    }

    await loadPartnerIdentity();

    await loadPartnerBots();
}

async function loadPartnerIdentity() {
    try {
        const data =
            await apiFirst([
                "/api/auth/me",
                "/api/auth/current",
            ]);

        setText(
            "partner-display-name",
            data.display_name ||
            data.username ||
            "Panel de Socio"
        );

    } catch (error) {
        console.debug(
            "Identidad partner no disponible:",
            error.message
        );
    }
}

async function loadPartnerBots() {
    const select =
        $("#partner-bot-select");

    const panel =
        $("#partner-bot-panel");

    const noBots =
        $("#partner-no-bots");

    if (!select) {
        return;
    }

    try {
        const data =
            await apiFirst([
                "/api/dashboard/partner",
                "/api/bots/mine",
                "/api/bots?scope=partner",
                "/api/bots",
            ]);

        let bots =
            firstArray(
                data,
                [
                    "bots",
                    "items",
                    "data"
                ]
            );

        if (
            !bots.length &&
            data?.bot &&
            typeof data.bot ===
                "object"
        ) {
            bots =
                [
                    data.bot
                ];
        }

        if (!bots.length) {
            select.innerHTML = `
                <option value="">
                    Sin bots asignados
                </option>
            `;

            panel.hidden =
                true;

            noBots.hidden =
                false;

            return;
        }

        noBots.hidden =
            true;

        select.innerHTML =
            bots.map(
                bot => `
                    <option
                        value="${bot.id}"
                    >
                        ${escapeHtml(
                            bot.display_name ||
                            bot.username ||
                            `BOT #${bot.id}`
                        )}
                    </option>
                `
            ).join("");

        select.onchange =
            () =>
                selectPartnerBot(
                    select.value,
                    bots
                );

        await selectPartnerBot(
            select.value ||
            bots[0].id,
            bots
        );

    } catch (error) {
        select.innerHTML = `
            <option value="">
                ${escapeHtml(
                    error.message
                )}
            </option>
        `;

        panel.hidden =
            true;

        noBots.hidden =
            false;
    }
}

async function selectPartnerBot(
    botId,
    cachedBots = []
) {
    GH.currentPartnerBotId =
        String(
            botId
        );

    const panel =
        $("#partner-bot-panel");

    if (!panel) {
        return;
    }

    let bot =
        cachedBots.find(
            item =>
                String(
                    item.id
                ) ===
                String(
                    botId
                )
        );

    if (!bot) {
        try {
            bot =
                await apiRequest(
                    `/api/bots/${botId}`
                );

        } catch {
            bot = {
                id:
                    botId
            };
        }
    }

    panel.hidden =
        false;

    renderPartnerBot(
        bot
    );

    await Promise.allSettled([
        loadPartnerStats(
            botId
        ),

        loadPartnerFounders(
            botId
        ),

        loadPartnerSettings(
            botId
        ),
    ]);
}

function renderPartnerBot(bot) {
    const enabled =
        bool(
            bot.enabled ??
            bot.is_enabled
        );

    setText(
        "partner-bot-name",
        bot.display_name ||
        bot.username ||
        `BOT #${bot.id}`
    );

    setText(
        "partner-bot-username",
        normalizeUsername(
            bot.username
        )
    );

    setText(
        "partner-bot-version",
        bot.version ||
        "—"
    );

    setText(
        "partner-bot-status",
        enabled
            ? "ONLINE"
            : "OFFLINE"
    );

    setText(
        "partner-power-title",
        bot.display_name ||
        bot.username ||
        "Bot"
    );

    const status =
        $("#partner-bot-status");

    setClassStatus(
        status,
        enabled
            ? "online"
            : "error"
    );

    const button =
        $("#partner-toggle-bot");

    if (button) {
        button.textContent =
            enabled
                ? "APAGAR BOT"
                : "ENCENDER BOT";

        button.dataset.enabled =
            String(
                enabled
            );

        button.onclick =
            () =>
                togglePartnerBot(
                    bot.id,
                    enabled
                );
    }
}

async function togglePartnerBot(
    botId,
    enabled
) {
    const button =
        $("#partner-toggle-bot");

    const alertBox =
        $("#partner-power-alert");

    hideAlert(
        alertBox
    );

    if (button) {
        button.disabled =
            true;
    }

    try {
        await apiFirst([
            {
                url:
                    `/api/bots/${botId}/${enabled ? "disable" : "enable"}`,

                options: {
                    method:
                        "POST"
                },
            },

            {
                url:
                    `/api/bots/${botId}`,

                options: {
                    method:
                        "PATCH",

                    body:
                        JSON.stringify({
                            enabled:
                                !enabled
                        }),
                },
            },
        ]);

        showAlert(
            alertBox,
            !enabled
                ? "Bot encendido correctamente."
                : "Bot apagado correctamente.",
            "success"
        );

        await loadPartnerBots();

    } catch (error) {
        showAlert(
            alertBox,
            error.message
        );

    } finally {
        if (button) {
            button.disabled =
                false;
        }
    }
}

async function loadPartnerStats(
    botId
) {
    try {
        const data =
            await apiFirst([
                `/api/statistics/bots/${botId}`,
                `/api/statistics/bot/${botId}`,
                `/api/dashboard/partner?bot_id=${encodeURIComponent(botId)}`,
            ]);

        setText(
            "partner-stat-users",
            formatNumber(
                data.users ??
                data.users_total ??
                data.total_users
            )
        );

        setText(
            "partner-stat-queries",
            formatNumber(
                data.queries_today ??
                data.today_queries ??
                data.queries
            )
        );

        setText(
            "partner-stat-credits",
            formatNumber(
                data.credits ??
                data.credits_total ??
                data.credits_in_circulation
            )
        );

    } catch (error) {
        console.debug(
            "Stats partner:",
            error.message
        );
    }
}

async function loadPartnerSettings(
    botId
) {
    try {
        const data =
            await apiFirst([
                `/api/bots/${botId}`,
                `/api/bots/${botId}/partner-settings`,
            ]);

        if (
            $("#partner-channel-url")
        ) {
            $("#partner-channel-url")
                .value =
                data.channel_url ||
                data.channel ||
                "";
        }

        if (
            $("#partner-group-url")
        ) {
            $("#partner-group-url")
                .value =
                data.group_url ||
                data.group ||
                "";
        }

    } catch (error) {
        console.debug(
            "Settings partner:",
            error.message
        );
    }
}

async function loadPartnerFounders(
    botId
) {
    const container =
        $("#partner-founders-list");

    if (!container) {
        return;
    }

    try {
        const data =
            await apiFirst([
                `/api/bots/${botId}/founders`,
                `/api/bots/${botId}/staff/founders`,
            ]);

        const items =
            firstArray(
                data,
                [
                    "items",
                    "founders",
                    "data"
                ]
            );

        if (!items.length) {
            container.innerHTML = `
                <div class="empty-state">
                    <p>
                        No hay fundadores o
                        cofundadores configurados.
                    </p>
                </div>
            `;

            return;
        }

        container.innerHTML =
            items.map(
                item => `
                    <div class="quick-action">

                        <span>
                            ${
                                String(
                                    item.role ||
                                    ""
                                ).toUpperCase() ===
                                "FUNDADOR"
                                    ? "👑"
                                    : "🤝"
                            }
                        </span>

                        <div style="flex:1">

                            <strong>
                                ${escapeHtml(
                                    String(
                                        item.role ||
                                        "STAFF"
                                    ).toUpperCase()
                                )}
                            </strong>

                            <small>
                                Telegram ID:
                                ${escapeHtml(
                                    item.telegram_id ||
                                    item.user_telegram_id ||
                                    item.id
                                )}
                            </small>

                        </div>

                        <button
                            class="btn-secondary founder-remove"
                            data-id="${escapeHtml(
                                item.telegram_id ||
                                item.user_telegram_id ||
                                item.id
                            )}"
                        >
                            QUITAR
                        </button>

                    </div>
                `
            ).join("");

        $$(".founder-remove")
            .forEach(
                button => {
                    button.addEventListener(
                        "click",
                        () =>
                            removePartnerFounder(
                                botId,
                                button.dataset.id
                            )
                    );
                }
            );

    } catch (error) {
        if (
            error
            instanceof ApiError &&
            [
                404,
                405
            ].includes(
                error.status
            )
        ) {
            container.innerHTML = `
                <div class="empty-state">
                    <p>
                        No hay contactos configurados.
                    </p>
                </div>
            `;
        } else {
            container.innerHTML = `
                <div class="empty-state">
                    <p>
                        ${escapeHtml(
                            error.message
                        )}
                    </p>
                </div>
            `;
        }
    }
}

async function removePartnerFounder(
    botId,
    telegramId
) {
    try {
        await apiFirst([
            {
                url:
                    `/api/bots/${botId}/founders/${telegramId}`,

                options: {
                    method:
                        "DELETE"
                },
            },

            {
                url:
                    `/api/bots/${botId}/founders`,

                options: {
                    method:
                        "DELETE",

                    body:
                        JSON.stringify({
                            telegram_id:
                                Number(
                                    telegramId
                                )
                        }),
                },
            },
        ]);

        await loadPartnerFounders(
            botId
        );

    } catch (error) {
        alert(
            error.message
        );
    }
}

function initPartnerForms() {
    const linksForm =
        $("#partner-links-form");

    linksForm?.addEventListener(
        "submit",
        async event => {
            event.preventDefault();

            const botId =
                GH.currentPartnerBotId;

            const alertBox =
                $("#partner-links-alert");

            hideAlert(
                alertBox
            );

            if (!botId) {
                return;
            }

            const payload = {
                channel_url:
                    $("#partner-channel-url")
                        ?.value.trim() ||
                    null,

                group_url:
                    $("#partner-group-url")
                        ?.value.trim() ||
                    null,
            };

            try {
                await apiFirst([
                    {
                        url:
                            `/api/bots/${botId}/partner-settings`,

                        options: {
                            method:
                                "PATCH",

                            body:
                                JSON.stringify(
                                    payload
                                ),
                        },
                    },

                    {
                        url:
                            `/api/bots/${botId}`,

                        options: {
                            method:
                                "PATCH",

                            body:
                                JSON.stringify(
                                    payload
                                ),
                        },
                    },
                ]);

                showAlert(
                    alertBox,
                    "Canal y grupo actualizados.",
                    "success"
                );

            } catch (error) {
                showAlert(
                    alertBox,
                    error.message
                );
            }
        }
    );

    const founderForm =
        $("#partner-founder-form");

    founderForm?.addEventListener(
        "submit",
        async event => {
            event.preventDefault();

            const botId =
                GH.currentPartnerBotId;

            const alertBox =
                $("#partner-founder-alert");

            hideAlert(
                alertBox
            );

            if (!botId) {
                return;
            }

            const telegramId =
                Number(
                    $("#partner-founder-id")
                        ?.value ||
                    0
                );

            const role =
                $("#partner-founder-role")
                    ?.value ||
                "COFUNDADOR";

            try {
                await apiRequest(
                    `/api/bots/${botId}/founders`,
                    {
                        method:
                            "POST",

                        body:
                            JSON.stringify({
                                telegram_id:
                                    telegramId,

                                role,
                            }),
                    }
                );

                founderForm.reset();

                showAlert(
                    alertBox,
                    "Contacto agregado correctamente.",
                    "success"
                );

                await loadPartnerFounders(
                    botId
                );

            } catch (error) {
                showAlert(
                    alertBox,
                    error.message
                );
            }
        }
    );
}

/* =========================================================
   REFRESH BUTTON DASHBOARD
   ========================================================= */

function initRefreshButtons() {
    $("#refresh-dashboard")
        ?.addEventListener(
            "click",
            loadMasterDashboard
        );
}

/* =========================================================
   START
   ========================================================= */

document.addEventListener(
    "DOMContentLoaded",
    () => {
        initLogin();

        initLogout();

        initSidebar();

        initGenericModals();

        initRefreshButtons();

        loadMasterDashboard();

        initSocios();

        initBots();

        initVersions();

        initCommands();

        initProvider();

        initPartnerPanel();

        initPartnerForms();
    }
);
