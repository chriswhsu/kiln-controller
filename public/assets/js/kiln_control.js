// Global Variables
let state = "----";
let state_last = "";
let graph = {profile: {}, live: {}};
let profiles = [];
let selected_profile = 0;
let selected_profile_name = "";
// F or C
let temp_scale = "";
let time_scale_slope = "s";
let time_scale_profile = "s";
let time_scale_long = "Seconds";
let temp_scale_display = "";
let kwh_rate = 0.0;
let currency_type = "";

// WebSocket Initialization
let protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
let host = `${protocol}//${window.location.hostname}:${window.location.port}`;
let ws_status = new WebSocket(`${host}/status`);
let ws_control = new WebSocket(`${host}/control`);
let ws_config = new WebSocket(`${host}/config`);
let ws_storage = new WebSocket(`${host}/storage`);

// Graph Setup
graph.profile = {
    label: "Profile",
    data: [],
    points: {show: false},
    color: "#75890c",
    draggable: false
};

graph.live = {
    label: "Live",
    data: [],
    points: {show: false},
    color: "#d8d3c5",
    draggable: false
};

// Function Definitions
function updateProfile(id) {
    selected_profile = id;
    selected_profile_name = profiles[id].name;
    let job_seconds = profiles[id].data.length === 0 ? 0 : parseInt(profiles[id].data[profiles[id].data.length - 1][0]);
    let kwh = (3850 * job_seconds / 3600 / 1000).toFixed(2);
    let cost = (kwh * kwh_rate).toFixed(2);
    let job_time = new Date(job_seconds * 1000).toISOString().slice(11, 19);
    $('#sel_prof').html(profiles[id].name);
    $('#sel_prof_eta').html(job_time);
    $('#sel_prof_cost').html(kwh + ' kWh (' + currency_type + cost + ')');
    graph.profile.data = profiles[id].data;
    graph.plot = $.plot("#graph_container", [graph.profile, graph.live], getOptions());
}

function deleteProfile() {
    let profile = {"type": "profile", "data": "", "name": selected_profile_name};
    let delete_struct = {"cmd": "DELETE", "profile": profile};

    let delete_cmd = JSON.stringify(delete_struct);
    console.log("Delete profile:" + selected_profile_name);

    ws_storage.send(delete_cmd);

    ws_storage.send('GET');
    selected_profile_name = profiles[0].name;

    state = "IDLE";
    $('#edit').hide();
    $('#profile_selector').show();
    $('#btn_controls').show();
    $('#status').slideDown();
    $('#profile_table').slideUp();
    $('#e2').select2('val', 0);
    graph.profile.points.show = false;
    graph.profile.draggable = false;
    graph.plot = $.plot("#graph_container", [graph.profile, graph.live], getOptions());
}

function updateProgress(percentage) {
    let progressBar = $('#progressBar');
    if (state === "RUNNING") {

        if (percentage > 100) percentage = 100;
        progressBar.css('width', percentage + '%');
        if (percentage > 5) progressBar.html(parseInt(percentage) + '%');
    } else {
        progressBar.css('width', 0 + '%');
        progressBar.html('');
    }
}

function updateProfileTable() {
    let dps = 0;
    let slope = "";
    let color = "";

    let html = '<h3>Schedule Points</h3><div class="table-responsive" style="overflow: hidden"><table class="table table-striped">';
    html += '<tr><th style="width: 50px">#</th><th>Target Time in ' + time_scale_long + '</th><th>Target Temperature in °' + temp_scale_display + '</th><th>Slope in &deg;' + temp_scale_display + '/' + time_scale_slope + '</th><th></th></tr>';

    for (let i = 0; i < graph.profile.data.length; i++) {

        if (i >= 1) dps = ((graph.profile.data[i][1] - graph.profile.data[i - 1][1]) / (graph.profile.data[i][0] - graph.profile.data[i - 1][0]) * 10) / 10;
        if (dps > 0) {
            slope = "up";
            color = "rgba(206, 5, 5, 1)";
        } else if (dps < 0) {
            slope = "down";
            color = "rgba(23, 108, 204, 1)";
            dps *= -1;
        } else if (dps === 0) {
            slope = "right";
            color = "grey";
        }

        html += '<tr><td><h4>' + (i + 1) + '</h4></td>';
        html += '<td><input type="text" class="form-control" id="profiletable-0-' + i + '" value="' + timeProfileFormatter(graph.profile.data[i][0], true) + '" style="width: 60px" /></td>';
        html += '<td><input type="text" class="form-control" id="profiletable-1-' + i + '" value="' + graph.profile.data[i][1] + '" style="width: 60px" /></td>';
        html += '<td><div class="input-group"><span class="glyphicon glyphicon-circle-arrow-' + slope + ' input-group-addon ds-trend" style="background: ' + color + '"></span><input type="text" class="form-control ds-input" readonly value="' + formatDPS(dps) + '" style="width: 100px" /></div></td>';
        html += '<td>&nbsp;</td></tr>';
    }

    html += '</table></div>';

    $('#profile_table').html(html);

    //Link table to graph
    $(".form-control").change(function () {
        let id = $(this)[0].id; //e.currentTarget.attributes.id
        let value = parseInt($(this)[0].value);
        let fields = id.split("-");
        let col = parseInt(fields[1]);
        let row = parseInt(fields[2]);

        if (graph.profile.data.length > 0) {
            if (col === 0) {
                graph.profile.data[row][col] = timeProfileFormatter(value, false);
            } else {
                graph.profile.data[row][col] = value;
            }

            graph.plot = $.plot("#graph_container", [graph.profile, graph.live], getOptions());
        }
        updateProfileTable();

    });
}

function timeProfileFormatter(val, down) {
    let rval = val
    switch (time_scale_profile) {
        case "m":
            if (down) {
                rval = val / 60;
            } else {
                rval = val * 60;
            }
            break;
        case "h":
            if (down) {
                rval = val / 3600;
            } else {
                rval = val * 3600;
            }
            break;
    }
    return Math.round(rval);
}

function formatDPS(val) {
    let tval = val;
    if (time_scale_slope === "m") {
        tval = val * 60;
    }
    if (time_scale_slope === "h") {
        tval = (val * 60) * 60;
    }
    return Math.round(tval);
}

function hazardTemp() {

    if (temp_scale === "f") {
        return (1500 * 9 / 5) + 32
    } else {
        return 1500
    }
}

function timeTickFormatter(val, axis) {
// hours
    if (axis.max > 3600) {
        //let hours = Math.floor(val / (3600));
        //return hours;
        return Math.floor(val / 3600);
    }

// minutes
    if (axis.max <= 3600) {
        return Math.floor(val / 60);
    }

// seconds
    if (axis.max <= 60) {
        return val;
    }
}

function runTask() {
    let cmd =
        {
            "cmd": "RUN",
            "profile": profiles[selected_profile]
        }

    graph.live.data = [];
    graph.plot = $.plot("#graph_container", [graph.profile, graph.live], getOptions());

    ws_control.send(JSON.stringify(cmd));

}

function runTaskSimulation() {
    let cmd =
        {
            "cmd": "SIMULATE",
            "profile": profiles[selected_profile]
        }

    graph.live.data = [];
    graph.plot = $.plot("#graph_container", [graph.profile, graph.live], getOptions());

    ws_control.send(JSON.stringify(cmd));

}


function abortTask() {
    let cmd = {"cmd": "STOP"};
    ws_control.send(JSON.stringify(cmd));
}

function enterNewMode() {
    state = "EDIT"
    $('#status').slideUp();
    $('#edit').show();
    $('#profile_selector').hide();
    $('#btn_controls').hide();
    $('#form_profile_name').attr('value', '').attr('placeholder', 'Please enter a name');
    graph.profile.points.show = true;
    graph.profile.draggable = true;
    graph.profile.data = [];
    graph.plot = $.plot("#graph_container", [graph.profile, graph.live], getOptions());
    updateProfileTable();
}

function enterEditMode() {
    state = "EDIT"
    $('#status').slideUp();
    $('#edit').show();
    $('#profile_selector').hide();
    $('#btn_controls').hide();
    $('#profile_table').slideDown();

    console.log(profiles);
    $('#form_profile_name').val(profiles[selected_profile].name);
    graph.profile.points.show = true;
    graph.profile.draggable = true;
    graph.plot = $.plot("#graph_container", [graph.profile, graph.live], getOptions());
    updateProfileTable();
}

function leaveEditMode() {
    selected_profile_name = $('#form_profile_name').val();
    ws_storage.send('GET');
    state = "IDLE";
    $('#edit').hide();
    $('#profile_selector').show();
    $('#btn_controls').show();
    $('#status').slideDown();
    $('#profile_table').slideUp();
    graph.profile.points.show = false;
    graph.profile.draggable = false;
    graph.plot = $.plot("#graph_container", [graph.profile, graph.live], getOptions());
}

function newPoint() {
    let pointx = 0;
    if (graph.profile.data.length > 0) {
        pointx = parseInt(graph.profile.data[graph.profile.data.length - 1][0]) + 15;
    }

    graph.profile.data.push([pointx, Math.floor((Math.random() * 230) + 25)]);
    graph.plot = $.plot("#graph_container", [graph.profile, graph.live], getOptions());
    updateProfileTable();
}


function delPoint() {
    graph.profile.data.splice(-1, 1)
    graph.plot = $.plot("#graph_container", [graph.profile, graph.live], getOptions());
    updateProfileTable();
}

function toggleTable() {
    $('#profile_table').slideToggle();
}

function saveProfile() {
    name = $('#form_profile_name').val();
    let rawdata = graph.plot.getData()[0].data
    let data = [];
    let last = -1;

    for (let i = 0; i < rawdata.length; i++) {
        if (rawdata[i][0] > last) {
            data.push([rawdata[i][0], rawdata[i][1]]);
        } else {
            $.bootstrapGrowl("<span class=\"glyphicon glyphicon-exclamation-sign\"></span> <b>ERROR 88:</b><br/>An oven is not a time-machine", {
                ele: 'body', // which element to append to
                type: 'alert', // (null, 'info', 'error', 'success')
                offset: {from: 'top', amount: 250}, // 'top', or 'bottom'
                align: 'center', // ('left', 'right', or 'center')
                width: 385, // (integer, or 'auto')
                delay: 5000,
                allow_dismiss: true,
                stackup_spacing: 10 // spacing between consecutively stacked growls.
            });

            return false;
        }

        last = rawdata[i][0];
    }

    let profile = {"type": "profile", "data": data, "name": name}
    let put = {"cmd": "PUT", "profile": profile}

    let put_cmd = JSON.stringify(put);

    ws_storage.send(put_cmd);

    leaveEditMode();
}

function get_tick_size() {
//switch(time_scale_profile){
//  case "s":
//    return 1;
//  case "m":
//    return 60;
//  case "h":
//    return 3600;
//  }
    return 3600;
}

function getOptions() {

    return {

        series:
            {
                lines:
                    {
                        show: true
                    },

                points:
                    {
                        show: true,
                        radius: 5,
                        symbol: "circle"
                    },

                shadowSize: 3

            },

        xaxis:
            {
                min: 0,
                tickColor: 'rgba(216, 211, 197, 0.2)',
                tickFormatter: timeTickFormatter,
                tickSize: get_tick_size(),
                font:
                    {
                        size: 14,
                        lineHeight: 14, weight: "normal",
                        family: "Digi",
                        variant: "small-caps",
                        color: "rgba(216, 211, 197, 0.85)"
                    }
            },

        yaxis:
            {
                min: 0,
                tickDecimals: 0,
                draggable: false,
                tickColor: 'rgba(216, 211, 197, 0.2)',
                font:
                    {
                        size: 14,
                        lineHeight: 14,
                        weight: "normal",
                        family: "Digi",
                        variant: "small-caps",
                        color: "rgba(216, 211, 197, 0.85)"
                    }
            },

        grid:
            {
                color: 'rgba(216, 211, 197, 0.55)',
                borderWidth: 1,
                labelMargin: 10,
                mouseActiveRadius: 50
            },

        legend:
            {
                show: false
            }
    };
}

function reconnectWebSocket(wsName) {
    console.log(`Lost connection to ${wsName}. Reloading the page...`);
    // Optionally, you can use a delay before the refresh
    setTimeout(function () {
        location.reload();
    }, 1000); // Refresh the page after 1 second
}

// Function to initialize a WebSocket with event handlers
function initializeWebSocket(wsName) {
    window[wsName].onopen = handleStatusOpen;
    window[wsName].onmessage = handleStatusMessage;
    window[wsName].onerror = handleStatusError;

    switch (wsName) {
        case 'ws_status':
            window[wsName].onclose = handleStatusClose;
            break;
        case 'ws_control':
            window[wsName].onclose = handleControlClose;
            break;
    }
}


function handleStatusOpen() {
    console.log("Status Socket has been opened");
    $.bootstrapGrowl("<span class=\"glyphicon glyphicon-exclamation-sign\"></span>Getting data from server", {
        ele: 'body',
        type: 'success',
        offset: {from: 'top', amount: 250},
        align: 'center',
        width: 385,
        delay: 2500,
        allow_dismiss: true,
        stackup_spacing: 10
    });
}




function handleStatusMessage(e) {
    console.log("received status data");
    console.log(e.data);
    let data = JSON.parse(e.data);  // This line was missing
    if (data.type === "backlog") {
        handleBacklogData(data);
    }

    if (state !== "EDIT") {
        updateApplicationState(data);
    }
}

function handleStatusClose() {
    $.bootstrapGrowl("<span class=\"glyphicon glyphicon-exclamation-sign\"></span> <b>ERROR 1:</b><br/>Status Websocket not available", {
        ele: 'body',
        type: 'error',
        offset: {from: 'top', amount: 250},
        align: 'center',
        width: 385,
        delay: 5000,
        allow_dismiss: true,
        stackup_spacing: 10
    });
    console.log("Status WebSocket closed. Attempting to reconnect...");
    reconnectWebSocket('ws_status', `${host}/status`);
}


function handleControlClose() {
    console.log("Control WebSocket closed. Attempting to reconnect...");
    reconnectWebSocket('ws_control', `${host}/control`);
}

function handleStatusError(error) {
    console.log("Status WebSocket encountered an error:", error);
    // Your existing error logic...
}

function handleBacklogData(data) {
    updateSelectedProfile(data.profile);
    updateGraphWithLogData(data.log);
}

function updateSelectedProfile(profileData) {
    if (profileData) {
        selected_profile_name = profileData.name;
        $.each(profiles, function (i, profile) {
            if (profile.name === profileData.name) {
                updateProfile(i);
                $('#e2').select2('val', i);
            }
        });
    }
}

function updateGraphWithLogData(logData) {
    $.each(logData, function (i, logEntry) {
        graph.live.data.push([logEntry.runtime, logEntry.temperature]);
    });
    graph.plot = $.plot("#graph_container", [graph.profile, graph.live], getOptions());
}

function updateApplicationState(data) {
    state = data.state;
    handleStateChange(data);
    updateUIElements(data);
}

function handleStateChange(data) {
    if (state !== state_last) {
        if (state_last === "RUNNING") {
            notifyRunCompleted(state);
        }
    }

    if (state === "RUNNING") {
        updateForRunningState(data);
    } else {
        updateForNonRunningState();
    }

    state_last = state;
}





function notifyRunCompleted(newState) {
    $('#target_temp').html('---');
    updateProgress(0);
    $.bootstrapGrowl("<span class=\"glyphicon glyphicon-exclamation-sign\"></span> <b>Run completed. New State: " + newState + "</b>", {
        ele: 'body', type: 'success', offset: {from: 'top', amount: 250},
        align: 'center', width: 385, delay: 0, allow_dismiss: true, stackup_spacing: 10
    });
}

function updateForRunningState(data) {
    $("#nav_start").hide();
    $("#nav_stop").show();

    graph.live.data.push([data.runtime, data.temperature]);
    graph.plot = $.plot("#graph_container", [graph.profile, graph.live], getOptions());

    let left = parseInt(data.total_time - data.runtime);
    let eta = new Date(left * 1000).toISOString().substr(11, 8);

    updateProgress(parseFloat(data.runtime) / parseFloat(data.total_time) * 100);
    $('#state').html('<span class="glyphicon glyphicon-time" style="font-size: 22px; font-weight: normal"></span><span> </span><span style="font-family: Digi,monospace; font-size: 40px;">' + eta + '</span>');
    $('#target_temp').html(parseInt(data.target));
    $('#cost').html(currency_type + parseFloat(data.cost).toFixed(2));
}

function updateForNonRunningState() {
    $("#nav_start").show();
    $("#nav_stop").hide();
    $('#state').html('<p class="ds-text">' + state + '</p>');
}

function updateUIElements(data) {
    $('#act_temp').html(parseInt(data.temperature));
    $('#heat').html('<div class="bar"></div>');

    updateHeatingIndicator(data.heat);
    updateHazardIndicator(data.temperature);
}

function updateHeatingIndicator(heatValue) {
    if (heatValue > 0) {
        $('#heat').addClass("ds-led-heat-active");
    } else {
        $('#heat').removeClass("ds-led-heat-active");
    }
}

function updateHazardIndicator(temperature) {
    if (temperature > hazardTemp()) {
        $('#hazard').addClass("ds-led-hazard-active");
    } else {
        $('#hazard').removeClass("ds-led-hazard-active");
    }
}


function setupConfigWebSocket() {
    ws_config.onopen = function () {
        // Request initial config on WebSocket open
        ws_config.send('GET');
    };

    ws_config.onmessage = function (e) {
        console.log("Config data received");
        console.log(e.data);

        let configData = JSON.parse(e.data);
        updateConfigDisplay(configData);
    };

    ws_config.onclose = function () {
        console.log("Config WebSocket closed");
        // Additional logic for WebSocket close, if needed
    };

    ws_config.onerror = function (error) {
        console.log("Config WebSocket error:", error);
        // Handle errors here
    };
}

function updateConfigDisplay(configData) {
    // Update temperature and timescale display based on received config
    temp_scale = configData.temp_scale;
    time_scale_slope = configData.time_scale_slope;
    time_scale_profile = configData.time_scale_profile;
    kwh_rate = configData.kwh_rate;
    currency_type = configData.currency_type;

    temp_scale_display = temp_scale === "c" ? "C" : "F";
    $('#act_temp_scale').html('º' + temp_scale_display);
    $('#target_temp_scale').html('º' + temp_scale_display);

    switch (time_scale_profile) {
        case "s":
            time_scale_long = "Seconds";
            break;
        case "m":
            time_scale_long = "Minutes";
            break;
        case "h":
            time_scale_long = "Hours";
            break;
    }
}

function setupControlWebSocket() {
    ws_control.onopen = function () {
        console.log("Control Socket has been opened");
        // Additional logic for WebSocket open, if needed
    };

    ws_control.onmessage = function (e) {
        console.log("Control data received");
        console.log(e.data);

        let controlData = JSON.parse(e.data);
        updateControlDisplay(controlData);
    };

    ws_control.onclose = function () {
        console.log("Control WebSocket closed");
        // Additional logic for WebSocket close, if needed
    };

    ws_control.onerror = function (error) {
        console.log("Control WebSocket error:", error);
        // Handle errors here
    };
}

function updateControlDisplay(controlData) {
    // Update the display based on control data
    // For example, updating live graph data
    graph.live.data.push([controlData.runtime, controlData.temperature]);
    graph.plot = $.plot("#graph_container", [graph.profile, graph.live], getOptions());

    // Additional logic to update UI based on control data
    // ...
}


function setupStorageWebSocket() {
    ws_storage.onopen = function () {
        console.log("Storage WebSocket opened");
        // Request initial profile data on WebSocket open
        ws_storage.send('GET');
    };

    ws_storage.onmessage = function (e) {
        console.log("Storage data received");
        console.log(e.data);

        let storageData = JSON.parse(e.data);
        handleStorageMessage(storageData);
    };

    ws_storage.onclose = function () {
        console.log("Storage WebSocket closed");
        // Additional logic for WebSocket close, if needed
    };

    ws_storage.onerror = function (error) {
        console.log("Storage WebSocket error:", error);
        // Handle errors here
    };
}

function handleStorageMessage(storageData) {
    // Check if the message is a response or an error
    if (storageData.resp && storageData.resp === "FAIL") {
        if (confirm('Overwrite?')) {
            storageData.force = true;
            console.log("Sending: " + JSON.stringify(storageData));
            ws_storage.send(JSON.stringify(storageData));
        }
        return;
    }

    // Handle profile data update
    if (Array.isArray(storageData)) {
        // Assuming storageData is an array of profiles
        profiles = storageData;
        updateProfileSelector();
    }

    // Additional logic to handle different types of storage messages
    // ...
}

function updateProfileSelector() {
    let e2 = $('#e2');
    e2.find('option').remove().end();

    let valid_profile_names = profiles.map(function (a) {
        return a.name;
    });

    if (valid_profile_names.length > 0 &&
        $.inArray(selected_profile_name, valid_profile_names) === -1) {
        selected_profile = 0;
        selected_profile_name = valid_profile_names[0];
    }

    profiles.forEach(function (profile, i) {
        e2.append('<option value="' + i + '">' + profile.name + '</option>');
        if (profile.name === selected_profile_name) {
            selected_profile = i;
            e2.select2('val', i);
            updateProfile(i);
        }
    });
}


function initializeProfileSelector() {
    let e2 = $('#e2');

    // Initialize the profile selector with select2 plugin
    e2.select2({
        placeholder: "Select Profile",
        allowClear: true,
        minimumResultsForSearch: -1
    });

    // Event handler for when a new profile is selected
    e2.on("change", function (e) {
        updateProfile(e.val);
    });

    // Additional initialization logic, if needed
    // ...
}


$(document).ready(function () {
    if (!("WebSocket" in window)) {
        $('#chatLog, input, button, #examples').fadeOut("fast");
        $('<p>Oh no, you need a browser that supports WebSockets. How about <a href="https://www.google.com/chrome">Google Chrome</a>?</p>').appendTo('#container');
    } else {
        // WebSocket URLs
        let protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        let host = `${protocol}//${window.location.hostname}:${window.location.port}`;

        // Initialize WebSocket connections
        window.ws_status = new WebSocket(`${host}/status`);
        window.ws_config = new WebSocket(`${host}/config`);
        window.ws_control = new WebSocket(`${host}/control`);
        window.ws_storage = new WebSocket(`${host}/storage`);

        // Assign event handlers
        initializeWebSocket('ws_status');
        setupConfigWebSocket(); // Assumes you have this function defined elsewhere
        setupControlWebSocket(); // Assumes you have this function defined elsewhere
        setupStorageWebSocket(); // Assumes you have this function defined elsewhere

        // Initialize Profile Selector
        initializeProfileSelector(); // Assumes you have this function defined elsewhere
    }
});



