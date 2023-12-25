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
let currency_type = "$";

// Graph Setup
graph.profile = {
    label: "Profile", data: [], points: {show: false}, color: "#75890c", draggable: false
};

graph.live = {
    label: "Live", data: [], points: {show: false}, color: "#d8d3c5", draggable: false
};

// Function Definitions
function updateProfile(id) {
    // Store the profile in a variable
    let profile = profiles[id];

    selected_profile = id;
    selected_profile_name = profile.name;
    let job_seconds = profile.data.length === 0 ? 0 : parseInt(profile.data[profile.data.length - 1][0]);
    let kwh = (3850 * job_seconds / 3600 / 1000).toFixed(2);
    let cost = (kwh * kwh_rate).toFixed(2);
    let job_time = new Date(job_seconds * 1000).toISOString().slice(11, 19);
    document.getElementById('sel_prof').textContent = profile.name;
    document.getElementById('sel_prof_eta').textContent = job_time;
    document.getElementById('sel_prof_cost').innerHTML = `${kwh} kWh (${currency_type}${cost})`;
    graph.profile.data = profile.data;
    graph.plot = $.plot("#graph_container", [graph.profile, graph.live], getOptions());
}

function formatNumber(number) {
    return number.toFixed(2);
}


function updateProgress(percentage) {
    let progressBar = $('#progressBar');
    if (state === "RUNNING" || state === "COMPLETE") {
        percentage = Math.min(percentage, 100);
        if (percentage === 100) {
            progressBar.addClass('no-animation'); // Add class to stop animation
        } else {
            progressBar.removeClass('no-animation'); // Remove class to allow animation
        }
        progressBar.css('width', percentage + '%');
        progressBar.html(Math.floor(percentage) + '%');
    } else if (state === "IDLE") {
        progressBar.css('width', '0%');
        progressBar.html('');
        progressBar.removeClass('no-animation'); // Ensure class is removed when idle
        graph.live.data.length = 0; // Clear the history line
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

    document.getElementById('profile_table').innerHTML = html;

    //Link table to graph
    let formControls = document.getElementsByClassName('form-control');
    Array.prototype.forEach.call(formControls, function (formControl) {
        formControl.addEventListener('change', function () {
            let id = this.id;
            let value = parseInt(this.value);
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


function enterNewMode() {
    console.log("Enter New Mode")
    state = "EDIT"
    $('#status').slideUp();
    $('#edit').show();
    $('#profile_selector').hide();
    $('#btn_controls').hide();
    $('#form_profile_name').val('').attr('placeholder', 'Please enter a name');
    graph.profile.points.show = true;
    graph.profile.draggable = true;
    graph.profile.data = [];
    graph.plot = $.plot("#graph_container", [graph.profile, graph.live], getOptions());
    updateProfileTable();
}

function enterEditMode() {
    console.log("Enter Edit Mode")
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

        series: {
            lines: {
                show: true
            }, points: {
                show: true, radius: 5, symbol: "circle"
            }, shadowSize: 3
        },

        xaxis: {
            min: 0, tickColor: 'rgba(216, 211, 197, 0.2)', tickFormatter: timeTickFormatter, tickSize: get_tick_size(), font: {
                size: 14, lineHeight: 14, weight: "normal", family: "Digi", variant: "small-caps", color: "rgba(216, 211, 197, 0.85)"
            }
        },

        yaxis: {
            min: 0, tickDecimals: 0, draggable: false, tickColor: 'rgba(216, 211, 197, 0.2)', font: {
                size: 14, lineHeight: 14, weight: "normal", family: "Digi", variant: "small-caps", color: "rgba(216, 211, 197, 0.85)"
            }
        },

        grid: {
            color: 'rgba(216, 211, 197, 0.55)', borderWidth: 1, labelMargin: 10, mouseActiveRadius: 50
        },

        legend: {
            show: false
        }
    };
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
        graph.live.data.push([logEntry.time_stamp, logEntry.temperature]);
    });
    graph.plot = $.plot("#graph_container", [graph.profile, graph.live], getOptions());
}


function updateRunIndicator(isSimulation, state) {
    const icon = document.getElementById('run_icon');
    const text = document.getElementById('run_text');
    const progressBar = document.getElementById('progressBar');

    // Clearing styles for non-specific states
    if (state !== "RUNNING" && state !== "COMPLETE") {
        icon.innerHTML = '';
        text.innerHTML = '';
        progressBar.style.backgroundColor = '';
        return;
    }

    // Setting styles specific to RUNNING state
    if (state === "RUNNING") {
        icon.innerHTML = isSimulation ? '🎛️' : '🔥';
        text.innerHTML = isSimulation ? 'Running Simulation' : 'Heating Kiln';
        text.style.color = isSimulation ? '#4aa3c4FF' : '#e70808';
        progressBar.style.backgroundColor = isSimulation ? '#4AA3C4' : '#e70808';
    }

    // Setting text for COMPLETE state
    if (state === "COMPLETE") {
        text.innerHTML = isSimulation ? 'Simulation Complete' : 'Kiln Run Complete';
    }
}


function updateUIElements(data) {
    $('#act_temp').html(parseFloat(data.temperature).toFixed(1));
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


function updateProfileSelector() {
    console.log('updateProfileSelector')
    let e2 = $('#e2');
    e2.find('option').remove().end();

    let valid_profile_names = profiles.map(function (a) {
        return a.name;
    });

    if (valid_profile_names.length > 0 && $.inArray(selected_profile_name, valid_profile_names) === -1) {
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
        placeholder: "Select Profile", allowClear: true, minimumResultsForSearch: -1
    });

    // Event handler for when a new profile is selected
    e2.on("change", function (e) {
        updateProfile(e.val);
    });
}


$(document).ready(function () {

    // Initialize Socket.IO client
    let socket = io(`${window.location.protocol}//${window.location.hostname}:${window.location.port}`);

    // Handle connection open
    socket.on('connect', function () {
        console.log("Connected to server via Socket.IO");

        console.log("Request Config Data")
        socket.emit('request_config'); // Request initial config on first connection
        socket.emit('request_backlog'); // Request initial backlog data on first connection
        socket.emit('request_profiles');

    });


    socket.on('oven_update', handleStatusUpdate);
    socket.on('backlog_data', handleBacklogData);
    socket.on('get_config', updateConfigDisplay);
    socket.on('control_response', updateControlDisplay);
    socket.on('profile_list', handleProfileList);
    socket.on('server_response', handleServerResponse)
    socket.on('error', handleServerResponse)


    // Handle connection errors
    socket.on('connect_error', function (error) {
        console.log("Connection Error: " + error);
    });

    // Handle disconnection
    socket.on('disconnect', function () {
        console.log("Disconnected from server");
        previouslyConnected = true; // Mark as previously connected for reconnection logic
    });

    // Bind the click events to the corresponding function
    $('#simulateButton').click(function () {
        runTaskSimulation();
    });

    $('#startRunButton').click(function () {
        runTask();
    });

    $('#nav_stop').click(function () {
        abortTask();
    });

    $('#save_profile').click(function () {
        saveProfile();
    });

    $('#delete_profile').click(function () {
        deleteProfile();
    });


    function runTask() {
        let cmd = {
            "cmd": "RUN", "profile": profiles[selected_profile]
        };
        graph.live.data = [];
        graph.plot = $.plot("#graph_container", [graph.profile, graph.live], getOptions());
        socket.emit('control', cmd); // Send command via Socket.IO
    }

    function runTaskSimulation() {
        let cmd = {
            "cmd": "SIMULATE", "profile": profiles[selected_profile]
        };

        graph.live.data = [];
        graph.plot = $.plot("#graph_container", [graph.profile, graph.live], getOptions());

        // Use Socket.IO to emit the command
        socket.emit('control', JSON.stringify(cmd));
    }

    function abortTask() {
        let cmd = {"cmd": "STOP"};
        socket.emit('control', JSON.stringify(cmd));
    }

    function handleStatusUpdate(data) {
        // Parse the incoming data
        console.log('handleStatusUpdate:' + data)
        let statusData = data;

        // Update global state
        state = statusData.state;

        // Handle state change
        if (state !== state_last) {
            if (state_last === "RUNNING" && state !== "RUNNING") {
                // Notify completion if the previous state was RUNNING
                notifyRunCompleted(statusData);
            }
            state_last = state;
        }

        updateApplicationState(data);

        // Update UI based on the current state
        if (state === "RUNNING" || state === "COMPLETE") {
            updateForRunningState(statusData);
        } else {
            updateForNonRunningState(statusData);
        }

        // Update the graph with live data
        if (statusData.time_stamp && statusData.temperature) {
            graph.live.data.push([statusData.time_stamp, statusData.temperature]);
            graph.plot = $.plot("#graph_container", [graph.profile, graph.live], getOptions());
        }
    }


    function updateApplicationState(data) {
        state = data.state;
        handleStateChange(data);
        updateUIElements(data);

        // Disable or enable profile selector, edit, and new profile button based on the state
        if (state !== "IDLE") {
            $('#e2, #btn_edit, #btn_new').prop('disabled', true).addClass('disabled-button');
        } else {
            $('#e2, #btn_edit, #btn_new').prop('disabled', false).removeClass('disabled-button');
        }
    }

    function handleStateChange(data) {
        // Check if state has changed from the last recorded state
        if (state !== state_last) {
            // Specific actions when transitioning out of the RUNNING state
            if (state_last === "RUNNING") {
                notifyRunCompleted(state, data.is_simulation);
            }

            // Update the last known state
            state_last = state;
        }

        // Perform actions based on the current state
        if (state === "RUNNING" || state === "COMPLETE") {
            updateForRunningState(data);
        } else {
            updateForNonRunningState(data);
        }
    }

    function notifyRunCompleted(data) {
        $('#target_temp').html('---');
        updateProgress(0);
        let completionMessage = data.is_simulation ? 'Simulation Complete' : 'Kiln Run Complete';
        $.bootstrapGrowl(completionMessage, {
            ele: 'body', type: 'success', offset: {from: 'top', amount: 250}, align: 'center', width: 385, delay: 5000, allow_dismiss: true, stackup_spacing: 10
        });
    }

    function updateForRunningState(data) {
        $("#nav_start").hide();
        $("#nav_stop").show();

        updateRunIndicator(data.is_simulation, data.state); // Pass the isSimulation flag and state
        graph.live.data.push([data.time_stamp, data.temperature]);
        graph.plot = $.plot("#graph_container", [graph.profile, graph.live], getOptions());

        let timeDisplay;
        if (data.state === "COMPLETE") {
            // Calculate elapsed time since completion
            let elapsedTime = new Date((data.time_stamp - data.total_time) * 1000).toISOString().substr(11, 8);
            timeDisplay = `<span>+${elapsedTime}</span>`;
        } else {
            // Normal time display
            let left = parseInt(data.total_time - data.time_stamp);
            let eta = new Date(left * 1000).toISOString().substr(11, 8);
            timeDisplay = `<span>${eta}</span>`;
        }

        updateProgress(parseFloat(data.time_stamp) / parseFloat(data.total_time) * 100);
        $('#state').html(timeDisplay);
        // Update target temperature display
        let targetTempDisplay = data.target === 0 ? '---' : parseFloat(data.target).toFixed(1);
        $('#target_temp').html(targetTempDisplay);
        $('#cost').html(currency_type + parseFloat(data.cost).toFixed(2));
    }

    function updateForNonRunningState(data) {
        // Update UI for non-running state
        $("#nav_start").show();
        $("#nav_stop").hide();
        updateRunIndicator(data.is_simulation, data.state);
        $('#state').html('<p class="ds-text">' + state + '</p>');

        // Reset progress bar if idle
        if (state === "IDLE") {
            updateProgress(0);
        }
    }

    function handleBacklogData(data) {
        updateSelectedProfile(data.profile);
        updateGraphWithLogData(data.log);
    }

    function updateConfigDisplay(configData) {
        console.log('updateConfigDisplay')
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

    function updateControlDisplay(controlData) {
        // Update the display based on control data
        // For example, updating live graph data
        graph.live.data.push([controlData.time_stamp, controlData.temperature]);
        graph.plot = $.plot("#graph_container", [graph.profile, graph.live], getOptions());
    }

    function handleServerResponse(response) {
        // You may want to add checks here to ensure 'response' has the right structure
        displayBootstrapGrowl(response.message, response.type, 3); // Assuming a 5-second delay
    }

    function displayBootstrapGrowl(message, type, delay_seconds) {
        $.bootstrapGrowl(message, {
            ele: 'body', // Element to append to
            type: type, // Can be 'info', 'error', 'success', etc.
            offset: {from: 'top', amount: 250}, // Positioning
            align: 'center', // Alignment
            width: 385, // Width of the growl message
            delay: delay_seconds * 1000, // Display duration in milliseconds
            allow_dismiss: true, // Allow the user to dismiss the growl
            stackup_spacing: 10 // Spacing between consecutively stacked growls
        });
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
                displayBootstrapGrowl("<span class=\"glyphicon glyphicon-exclamation-sign\"></span> <b>ERROR 88:</b><br/>An oven is not a time-machine", 5)
                return false;
            }
            last = rawdata[i][0];
        }

        let profile = {"type": "profile", "data": data, "name": name}
        let put = {"cmd": "PUT", "profile": profile}

        let put_cmd = JSON.stringify(put);

        socket.emit('save_profile', put);

        leaveEditMode();
    }

    function handleProfileList(storageData) {
        // Check if the message is a response or an error
        console.log('handleProfileList');
        console.log(storageData)
        try {
            let profilesArray = JSON.parse(storageData);
            if (Array.isArray(profilesArray)) {
                profiles = profilesArray;
                updateProfileSelector();
            } else {
                console.error("Received data is not an array.");
            }
        } catch (error) {
            console.error("Error parsing received data: ", error);
        }

        // Additional logic to handle different types of storage messages
        // ...
    }

    // Initialize Profile Selector remains the same
    initializeProfileSelector();


    function deleteProfile() {

        console.log("Delete profile:" + selected_profile_name);

        socket.emit('delete_profile', selected_profile_name);

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
});
