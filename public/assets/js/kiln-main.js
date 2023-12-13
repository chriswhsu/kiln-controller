// main.js

$(document).ready(function () {
    // Check if the browser supports WebSockets
    if (!("WebSocket" in window)) {
        $('#chatLog, input, button, #examples').fadeOut("fast");
        $('<p>Oh no, you need a browser that supports WebSockets. How about <a href="https://www.google.com/chrome">Google Chrome</a>?</p>').appendTo('#container');
    } else {
        // Initialize WebSocket connections and the graph
        initializeWebSockets();
        initializeGraph();

        // Initialize Profile Selector
        initializeProfileSelector();
    }
});
