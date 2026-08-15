"use strict";

/* =========================================================
   GUARDIAHEXBOT PLATFORM
   REALTIME CLIENT - WEBSOCKETS

   MASTER:
   /realtime/ws/master

   PARTNER:
   /realtime/ws/partner
   /realtime/ws/partner/{bot_id}
   ========================================================= */

const GHRealtime = {

    socket: null,

    connected: false,

    connecting: false,

    stopped: false,

    reconnectTimer: null,

    refreshTimer: null,

    reconnectAttempts: 0,

    candidateIndex: 0,

    currentUrl: null,

    maxReconnectDelay: 30000,

};


/* =========================================================
   HELPERS
   ========================================================= */

function realtimeToken() {

    return (
        localStorage.getItem(
            "guardiahex_access_token"
        ) || ""
    );

}


function realtimeRole() {

    return (
        localStorage.getItem(
            "guardiahex_role"
        ) || ""
    ).toUpperCase();

}


function realtimePartnerBotId() {

    try {

        if (
            typeof GH !== "undefined" &&
            GH.currentPartnerBotId
        ) {

            return String(
                GH.currentPartnerBotId
            );

        }

    } catch (_) {

        // Ignorar.
    }


    const select =
        document.getElementById(
            "partner-bot-select"
        );


    if (
        select &&
        select.value
    ) {

        return String(
            select.value
        );

    }


    return "";

}


function websocketProtocol() {

    return (
        window.location.protocol ===
        "https:"
    )
        ? "wss:"
        : "ws:";

}


function websocketBase() {

    return (
        `${websocketProtocol()}//` +
        window.location.host
    );

}


function buildWsUrl(path) {

    const token =
        realtimeToken();


    const url =
        new URL(
            websocketBase() + path
        );


    /*
     * El backend actual autentica WebSocket
     * mediante ?token=JWT.
     *
     * El token no se imprime en consola.
     */

    url.searchParams.set(
        "token",
        token
    );


    return url.toString();

}


/* =========================================================
   RUTAS
   ========================================================= */

function websocketCandidates() {

    const role =
        realtimeRole();


    const isMasterPage =
        Boolean(
            document.querySelector(
                ".panel-page"
            )
        );


    const isPartnerPage =
        Boolean(
            document.getElementById(
                "partner-bot-select"
            )
        );


    const botId =
        realtimePartnerBotId();


    /*
     * Se incluyen rutas con /api y sin /api
     * para que funcione aunque FastAPI monte
     * el router realtime dentro de /api.
     */

    if (
        role === "SUPERADMIN" ||
        (
            isMasterPage &&
            !isPartnerPage
        )
    ) {

        return [

            "/api/realtime/ws/master",

            "/realtime/ws/master",

        ];

    }


    if (isPartnerPage) {

        const paths = [];


        if (botId) {

            paths.push(
                `/api/realtime/ws/partner/${encodeURIComponent(botId)}`
            );

            paths.push(
                `/realtime/ws/partner/${encodeURIComponent(botId)}`
            );

        }


        paths.push(
            "/api/realtime/ws/partner"
        );

        paths.push(
            "/realtime/ws/partner"
        );


        return paths;

    }


    return [];

}


/* =========================================================
   ESTADO VISUAL
   ========================================================= */

function setRealtimeState(
    state
) {

    const status =
        document.getElementById(
            "websocket-status"
        );


    const indicators =
        Array.from(
            document.querySelectorAll(
                ".live-indicator"
            )
        );


    if (status) {

        status.classList.remove(
            "status-online",
            "status-pending",
            "status-error"
        );


        if (
            state === "connected"
        ) {

            status.textContent =
                "CONECTADO";

            status.classList.add(
                "status-online"
            );

        }

        else if (
            state === "connecting"
        ) {

            status.textContent =
                "CONECTANDO";

            status.classList.add(
                "status-pending"
            );

        }

        else if (
            state === "reconnecting"
        ) {

            status.textContent =
                "RECONECTANDO";

            status.classList.add(
                "status-pending"
            );

        }

        else {

            status.textContent =
                "OFFLINE";

            status.classList.add(
                "status-error"
            );

        }

    }


    indicators.forEach(
        element => {

            element.dataset
                .realtimeState =
                state;


            if (
                state === "connected"
            ) {

                element.title =
                    "Conexión en tiempo real activa";

            }

            else if (
                state === "connecting" ||
                state === "reconnecting"
            ) {

                element.title =
                    "Reconectando sistema en tiempo real";

            }

            else {

                element.title =
                    "Conexión en tiempo real desconectada";

            }

        }
    );

}


/* =========================================================
   CONEXIÓN
   ========================================================= */

function connectRealtime() {

    if (
        GHRealtime.stopped ||
        GHRealtime.connecting ||
        GHRealtime.connected
    ) {

        return;

    }


    const token =
        realtimeToken();


    if (!token) {

        return;

    }


    const candidates =
        websocketCandidates();


    if (!candidates.length) {

        return;

    }


    if (
        GHRealtime.candidateIndex >=
        candidates.length
    ) {

        GHRealtime.candidateIndex =
            0;

    }


    const path =
        candidates[
            GHRealtime.candidateIndex
        ];


    const url =
        buildWsUrl(
            path
        );


    GHRealtime.connecting =
        true;


    GHRealtime.currentUrl =
        path;


    setRealtimeState(
        GHRealtime.reconnectAttempts > 0
            ? "reconnecting"
            : "connecting"
    );


    let opened =
        false;


    try {

        GHRealtime.socket =
            new WebSocket(
                url
            );

    }

    catch (_) {

        GHRealtime.connecting =
            false;

        tryNextRealtimeCandidate();

        return;

    }


    const socket =
        GHRealtime.socket;


    socket.addEventListener(
        "open",
        () => {

            opened =
                true;


            GHRealtime.connected =
                true;


            GHRealtime.connecting =
                false;


            GHRealtime.reconnectAttempts =
                0;


            /*
             * Ya encontramos una ruta válida.
             * Conservamos este índice.
             */

            setRealtimeState(
                "connected"
            );


            window.dispatchEvent(
                new CustomEvent(
                    "guardiahex:realtime-connected",
                    {
                        detail: {
                            path:
                                GHRealtime.currentUrl
                        }
                    }
                )
            );

        }
    );


    socket.addEventListener(
        "message",
        event => {

            handleRealtimeMessage(
                event.data
            );

        }
    );


    socket.addEventListener(
        "error",
        () => {

            /*
             * El evento close será quien
             * gestione reconexión.
             */

        }
    );


    socket.addEventListener(
        "close",
        () => {

            GHRealtime.connected =
                false;


            GHRealtime.connecting =
                false;


            GHRealtime.socket =
                null;


            if (
                GHRealtime.stopped
            ) {

                setRealtimeState(
                    "offline"
                );

                return;

            }


            /*
             * Si nunca llegó a abrir, probablemente
             * esta variante de ruta no existe.
             * Probamos la siguiente.
             */

            if (!opened) {

                tryNextRealtimeCandidate();

                return;

            }


            scheduleRealtimeReconnect();

        }
    );

}


/* =========================================================
   PROBAR SIGUIENTE RUTA
   ========================================================= */

function tryNextRealtimeCandidate() {

    const candidates =
        websocketCandidates();


    if (!candidates.length) {

        setRealtimeState(
            "offline"
        );

        return;

    }


    GHRealtime.candidateIndex++;


    if (
        GHRealtime.candidateIndex <
        candidates.length
    ) {

        clearTimeout(
            GHRealtime.reconnectTimer
        );


        GHRealtime.reconnectTimer =
            setTimeout(
                connectRealtime,
                500
            );


        return;

    }


    /*
     * Se probaron todas.
     * Volvemos al inicio y esperamos.
     */

    GHRealtime.candidateIndex =
        0;


    scheduleRealtimeReconnect();

}


/* =========================================================
   RECONEXIÓN AUTOMÁTICA
   ========================================================= */

function scheduleRealtimeReconnect() {

    if (
        GHRealtime.stopped
    ) {

        return;

    }


    clearTimeout(
        GHRealtime.reconnectTimer
    );


    GHRealtime.reconnectAttempts++;


    const delay =
        Math.min(
            GHRealtime.maxReconnectDelay,

            1000 *
            Math.pow(
                2,
                Math.min(
                    GHRealtime.reconnectAttempts,
                    5
                )
            )
        );


    setRealtimeState(
        "reconnecting"
    );


    GHRealtime.reconnectTimer =
        setTimeout(
            connectRealtime,
            delay
        );

}


/* =========================================================
   DESCONECTAR
   ========================================================= */

function disconnectRealtime(
    permanent = false
) {

    clearTimeout(
        GHRealtime.reconnectTimer
    );


    GHRealtime.stopped =
        permanent;


    GHRealtime.connected =
        false;


    GHRealtime.connecting =
        false;


    if (
        GHRealtime.socket
    ) {

        try {

            GHRealtime.socket.close(
                1000,
                "Client disconnect"
            );

        }

        catch (_) {

            // Ignorar.
        }

    }


    GHRealtime.socket =
        null;


    setRealtimeState(
        "offline"
    );

}


/* =========================================================
   RECONECTAR
   ========================================================= */

function restartRealtime() {

    disconnectRealtime(
        false
    );


    GHRealtime.stopped =
        false;


    GHRealtime.reconnectAttempts =
        0;


    GHRealtime.candidateIndex =
        0;


    setTimeout(
        connectRealtime,
        300
    );

}


/* =========================================================
   PARSEO DE EVENTOS
   ========================================================= */

function parseRealtimePayload(
    raw
) {

    if (
        typeof raw !==
        "string"
    ) {

        return raw;

    }


    try {

        return JSON.parse(
            raw
        );

    }

    catch (_) {

        return {
            type:
                "message",

            data:
                raw
        };

    }

}


/* =========================================================
   MANEJO DE EVENTOS
   ========================================================= */

function handleRealtimeMessage(
    raw
) {

    const payload =
        parseRealtimePayload(
            raw
        );


    if (!payload) {

        return;

    }


    const type =
        String(
            payload.type ||
            payload.event ||
            payload.name ||
            "update"
        ).toLowerCase();


    /*
     * Si el servidor manda ping, respondemos
     * únicamente cuando existe conexión.
     */

    if (
        type === "ping"
    ) {

        try {

            if (
                GHRealtime.socket &&
                GHRealtime.socket.readyState ===
                    WebSocket.OPEN
            ) {

                GHRealtime.socket.send(
                    JSON.stringify({
                        type:
                            "pong"
                    })
                );

            }

        }

        catch (_) {

            // Ignorar.
        }


        return;

    }


    if (
        type === "pong"
    ) {

        return;

    }


    /*
     * Exponer todos los eventos al resto
     * del frontend.
     */

    window.dispatchEvent(
        new CustomEvent(
            "guardiahex:realtime",
            {
                detail:
                    payload
            }
        )
    );


    processRealtimeEvent(
        type,
        payload
    );

}


/* =========================================================
   ACTUALIZACIONES
   ========================================================= */

function processRealtimeEvent(
    type,
    payload
) {

    const botId =
        String(
            payload.bot_id ||
            payload.data?.bot_id ||
            payload.bot?.id ||
            ""
        );


    const currentPartnerBot =
        realtimePartnerBotId();


    /*
     * BOT
     */

    if (
        type.includes("bot")
    ) {

        realtimeRefresh(
            "bots"
        );


        realtimeRefresh(
            "dashboard"
        );


        realtimeRefresh(
            "versions"
        );


        if (
            !botId ||
            !currentPartnerBot ||
            botId ===
                currentPartnerBot
        ) {

            realtimeRefresh(
                "partner"
            );

        }

    }


    /*
     * ESTADÍSTICAS / CONSULTAS
     */

    if (
        type.includes(
            "stat"
        ) ||
        type.includes(
            "query"
        ) ||
        type.includes(
            "consulta"
        ) ||
        type.includes(
            "credit"
        ) ||
        type.includes(
            "transaction"
        ) ||
        type.includes(
            "subscription"
        ) ||
        type.includes(
            "seller"
        )
    ) {

        realtimeRefresh(
            "dashboard"
        );


        if (
            !botId ||
            !currentPartnerBot ||
            botId ===
                currentPartnerBot
        ) {

            realtimeRefresh(
                "partner-stats"
            );

        }

    }


    /*
     * SOCIOS
     */

    if (
        type.includes(
            "socio"
        ) ||
        type.includes(
            "partner.created"
        ) ||
        type.includes(
            "partner.updated"
        )
    ) {

        realtimeRefresh(
            "socios"
        );


        realtimeRefresh(
            "dashboard"
        );

    }


    /*
     * COMANDOS
     */

    if (
        type.includes(
            "command"
        ) ||
        type.includes(
            "cmd"
        )
    ) {

        realtimeRefresh(
            "commands"
        );

    }


    /*
     * API CENTRAL
     */

    if (
        type.includes(
            "provider"
        ) ||
        type.includes(
            "api."
        )
    ) {

        realtimeRefresh(
            "provider"
        );

    }


    /*
     * FUNDADORES
     */

    if (
        type.includes(
            "founder"
        ) ||
        type.includes(
            "cofounder"
        ) ||
        type.includes(
            "staff"
        )
    ) {

        if (
            !botId ||
            !currentPartnerBot ||
            botId ===
                currentPartnerBot
        ) {

            realtimeRefresh(
                "partner-founders"
            );

        }

    }


    /*
     * CONFIGURACIÓN PARTNER
     */

    if (
        type.includes(
            "settings"
        ) ||
        type.includes(
            "channel"
        ) ||
        type.includes(
            "group"
        )
    ) {

        if (
            !botId ||
            !currentPartnerBot ||
            botId ===
                currentPartnerBot
        ) {

            realtimeRefresh(
                "partner-settings"
            );

        }

    }


    /*
     * Evento genérico.
     */

    if (
        type === "update" ||
        type === "refresh" ||
        type === "system.update"
    ) {

        realtimeRefresh(
            "visible"
        );

    }

}


/* =========================================================
   REFRESH DEBOUNCED
   ========================================================= */

const realtimeRefreshQueue =
    new Set();


function realtimeRefresh(
    section
) {

    realtimeRefreshQueue.add(
        section
    );


    clearTimeout(
        GHRealtime.refreshTimer
    );


    GHRealtime.refreshTimer =
        setTimeout(
            flushRealtimeRefresh,
            300
        );

}


async function flushRealtimeRefresh() {

    const sections =
        new Set(
            realtimeRefreshQueue
        );


    realtimeRefreshQueue.clear();


    /*
     * Dashboard
     */

    if (
        sections.has(
            "dashboard"
        ) ||
        sections.has(
            "visible"
        )
    ) {

        if (
            typeof loadMasterDashboard ===
                "function" &&
            document.getElementById(
                "stat-bots-total"
            )
        ) {

            Promise.resolve(
                loadMasterDashboard()
            ).catch(
                () => {}
            );

        }

    }


    /*
     * Socios
     */

    if (
        sections.has(
            "socios"
        ) ||
        sections.has(
            "visible"
        )
    ) {

        if (
            typeof loadSocios ===
                "function" &&
            document.getElementById(
                "socios-table-body"
            )
        ) {

            Promise.resolve(
                loadSocios()
            ).catch(
                () => {}
            );

        }

    }


    /*
     * Bots
     */

    if (
        sections.has(
            "bots"
        ) ||
        sections.has(
            "visible"
        )
    ) {

        if (
            typeof loadBots ===
                "function" &&
            document.getElementById(
                "master-bots-container"
            )
        ) {

            Promise.resolve(
                loadBots()
            ).catch(
                () => {}
            );

        }

    }


    /*
     * Versiones
     */

    if (
        sections.has(
            "versions"
        ) ||
        sections.has(
            "visible"
        )
    ) {

        if (
            typeof loadVersionsBots ===
                "function" &&
            document.getElementById(
                "versions-bots-table"
            )
        ) {

            Promise.resolve(
                loadVersionsBots()
            ).catch(
                () => {}
            );

        }

    }


    /*
     * Commands
     */

    if (
        sections.has(
            "commands"
        ) ||
        sections.has(
            "visible"
        )
    ) {

        if (
            typeof loadCommands ===
                "function" &&
            document.getElementById(
                "commands-table-body"
            )
        ) {

            Promise.resolve(
                loadCommands()
            ).catch(
                () => {}
            );

        }

    }


    /*
     * Provider
     */

    if (
        sections.has(
            "provider"
        ) ||
        sections.has(
            "visible"
        )
    ) {

        if (
            typeof loadProviderStatus ===
                "function" &&
            (
                document.getElementById(
                    "provider-main-status"
                ) ||
                document.getElementById(
                    "provider-status"
                )
            )
        ) {

            Promise.resolve(
                loadProviderStatus()
            ).catch(
                () => {}
            );

        }

    }


    /*
     * Partner completo
     */

    if (
        sections.has(
            "partner"
        ) ||
        sections.has(
            "visible"
        )
    ) {

        if (
            document.getElementById(
                "partner-bot-select"
            ) &&
            typeof loadPartnerBots ===
                "function"
        ) {

            Promise.resolve(
                loadPartnerBots()
            ).catch(
                () => {}
            );

        }

    }


    const partnerBot =
        realtimePartnerBotId();


    /*
     * Partner stats
     */

    if (
        partnerBot &&
        sections.has(
            "partner-stats"
        )
    ) {

        if (
            typeof loadPartnerStats ===
                "function"
        ) {

            Promise.resolve(
                loadPartnerStats(
                    partnerBot
                )
            ).catch(
                () => {}
            );

        }

    }


    /*
     * Partner founders
     */

    if (
        partnerBot &&
        sections.has(
            "partner-founders"
        )
    ) {

        if (
            typeof loadPartnerFounders ===
                "function"
        ) {

            Promise.resolve(
                loadPartnerFounders(
                    partnerBot
                )
            ).catch(
                () => {}
            );

        }

    }


    /*
     * Partner settings
     */

    if (
        partnerBot &&
        sections.has(
            "partner-settings"
        )
    ) {

        if (
            typeof loadPartnerSettings ===
                "function"
        ) {

            Promise.resolve(
                loadPartnerSettings(
                    partnerBot
                )
            ).catch(
                () => {}
            );

        }

    }

}


/* =========================================================
   CAMBIO DE BOT PARTNER
   ========================================================= */

function watchPartnerBotSelector() {

    const select =
        document.getElementById(
            "partner-bot-select"
        );


    if (!select) {

        return;

    }


    select.addEventListener(
        "change",
        () => {

            /*
             * El backend tiene endpoint específico
             * /partner/{bot_id}.
             * Al cambiar bot, renovamos WS.
             */

            setTimeout(
                restartRealtime,
                250
            );

        }
    );

}


/* =========================================================
   VISIBILIDAD / RED
   ========================================================= */

function initRealtimeLifecycle() {

    window.addEventListener(
        "online",
        () => {

            GHRealtime.stopped =
                false;


            restartRealtime();

        }
    );


    window.addEventListener(
        "offline",
        () => {

            disconnectRealtime(
                false
            );

        }
    );


    document.addEventListener(
        "visibilitychange",
        () => {

            if (
                document.visibilityState ===
                    "visible" &&
                !GHRealtime.connected &&
                navigator.onLine
            ) {

                restartRealtime();

            }

        }
    );


    window.addEventListener(
        "beforeunload",
        () => {

            GHRealtime.stopped =
                true;


            if (
                GHRealtime.socket
            ) {

                try {

                    GHRealtime.socket.close(
                        1000,
                        "Page unload"
                    );

                }

                catch (_) {

                    // Ignorar.
                }

            }

        }
    );

}


/* =========================================================
   START
   ========================================================= */

function initRealtime() {

    /*
     * Login no necesita WebSocket.
     */

    if (
        document.getElementById(
            "login-form"
        )
    ) {

        return;

    }


    if (
        !realtimeToken()
    ) {

        setRealtimeState(
            "offline"
        );

        return;

    }


    watchPartnerBotSelector();


    initRealtimeLifecycle();


    /*
     * Esperamos un instante para permitir que
     * app.js cargue el bot del socio primero.
     */

    setTimeout(
        connectRealtime,
        500
    );

}


/* =========================================================
   API PÚBLICA DEL CLIENTE REALTIME
   ========================================================= */

window.GHRealtime = {

    connect:
        connectRealtime,

    disconnect:
        disconnectRealtime,

    restart:
        restartRealtime,

    refresh:
        realtimeRefresh,

    get connected() {

        return (
            GHRealtime.connected
        );

    },

};


/* =========================================================
   DOM READY
   ========================================================= */

document.addEventListener(
    "DOMContentLoaded",
    initRealtime
);
