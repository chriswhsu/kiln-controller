// websockets.js

// Initialize WebSocket connections
function initializeWebSockets() {
    let protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    let host = `${protocol}//${window.location.hostname}:${window.location.port}`;

    window.ws_status = new WebSocket(`${host}/status`);
    window.ws_config = new WebSocket(`${host}/config`);
    window.ws_control = new WebSocket(`${host}/control`);
    window.ws_storage = new WebSocket(`${host}/storage`);

    initializeWebSocket('ws_status');
    initializeWebSocket('ws_config');
    initializeWebSocket('ws_control');
    initializeWebSocket('ws_storage');
}

// General function to initialize a WebSocket with event handlers
function initializeWebSocket(wsName) {
    window[wsName].onopen = function(event) {
        handleWebSocketOpen(wsName, event);
    };
    window[wsName].onmessage = function(event) {
        handleWebSocketMessage(wsName, event);
    };
    window[wsName].onerror = function(error) {
        handleWebSocketError(wsName, error);
    };
    window[wsName].onclose = function(event) {
        handleWebSocketClose(wsName, event);
    };
}

// WebSocket Event Handlers

function handleWebSocketOpen(wsName, event) {
    console.log(`WebSocket ${wsName} opened:`, event);
    // Additional open logic...
}
function handleWebSocketMessage(wsName, event) {
    console.log(`WebSocket ${wsName} message:`, event.data);

    let message;
    try {
        message = JSON.parse(event.data);
    } catch (error) {
        console.error(`Error parsing message from WebSocket ${wsName}:`, error);
        return;
    }

    switch (wsName) {
        case 'ws_status':
            handleStatusWebSocketMessage(message);
            break;
        case 'ws_control':
            handleControlWebSocketMessage(message);
            break;
        case 'ws_config':
            handleConfigWebSocketMessage(message);
            break;
        case 'ws_storage':
            handleStorageWebSocketMessage(message);
            break;
        default:
            console.warn(`Unhandled WebSocket name: ${wsName}`);
            break;
    }
}

function handleStatusWebSocketMessage(message) {
    if (message.type === "update") {
        // Example: Update some status indicators in the UI
        $('#status-indicator').text(message.status);
    }
}

function handleControlWebSocketMessage(message) {
    if (message.type === "response") {
        // Example: Handle a response from a control command
        if (message.success) {
            console.log("Control command executed successfully.");
        } else {
            console.error("Control command failed:", message.error);
        }
    }
}

function handleConfigWebSocketMessage(message) {
    if (message.type === "configData") {
        // Example: Update configuration settings
        temp_scale = message.temp_scale;
        time_scale_slope = message.time_scale_slope;
        time_scale_profile = message.time_scale_profile;
        kwh_rate = message.kwh_rate;
        currency_type = message.currency_type;
        updateConfigDisplay(); // Assuming there's a function to update the display
    }
}

function handleStorageWebSocketMessage(message) {
    if (message.type === "profileData") {
        // Example: Update the profiles array and refresh the profile selector
        profiles = message.profiles;
        updateProfileSelector(); // Assuming there's a function to update the profile selector
    }
}

function updateConfigDisplay() {
    // Update the UI based on the new configuration settings
    $('#temp_scale_display').text(temp_scale);
    // ... update other configuration displays
}



function handleWebSocketError(wsName, error) {
    console.log(`WebSocket ${wsName} error:`, error);
    // Additional error handling logic...
}

function handleWebSocketClose(wsName, event) {
    console.log(`WebSocket ${wsName} closed:`, event);
    // Attempt to reconnect or other close logic...
    reconnectWebSocket(wsName);
}

// Function to handle WebSocket reconnection
function reconnectWebSocket(wsName) {
    console.log(`Attempting to reconnect WebSocket ${wsName}...`);
    // Reconnect logic...
}

// Export functions if using ES6 modules
// export { initializeWebSockets, handleWebSocketOpen, handleWebSocketMessage, handleWebSocketError, handleWebSocketClose, reconnectWebSocket };
