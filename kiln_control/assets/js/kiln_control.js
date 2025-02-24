// Global Variables
let currentState = "----";
let lastState = "";
let graph = {profile: {}, live: {}};
let profiles = [];
let selectedProfile = 0;
let selectedProfileName = "";
// F or C
let tempScale = "";
let timeScaleSlope = "";
let timeScaleProfile = "";
let timeScaleLong = "";
let tempScaleDisplay = "";
let kwh_rate = 0.0;
let currency_type = "$";

const RUNNING = "RUNNING";
const IDLE = "IDLE";
const COMPLETE = "COMPLETE";
const ABORTED = "ABORTED";


// Graph Setup
graph.profile = {
    label: "Profile", data: [], points: {show: false}, color: "#75890c", draggable: false
};

graph.live = {
    label: "Live", data: [], points: {show: false}, color: "#d8d3c5", draggable: false
};

// Function Definitions
function updateProfile(profileId) {
    // Store the profile in a variable
    let profile = profiles[profileId];

    selectedProfile = profileId;
    selectedProfileName = profile.name;
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

function updateProgress(percentage) {
    let progressBar = $('#progressBar');
    if (currentState === RUNNING || currentState === COMPLETE) {
        percentage = Math.min(percentage, 100);
        if (percentage === 100) {
            progressBar.addClass('no-animation'); // Add class to stop animation
        } else {
            progressBar.removeClass('no-animation'); // Remove class to allow animation
        }
        progressBar.css('width', percentage + '%');
        progressBar.html(Math.floor(percentage) + '%');
    } else if (currentState === IDLE) {
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
    html += '<tr><th style="width: 50px">#</th><th>Target Time in ' + timeScaleLong + '</th><th>Target Temperature in °' + tempScaleDisplay + '</th><th>Desired Slope (+/-) </th> <th>Slope in &deg;' + tempScaleDisplay + ' / ' + timeScaleSlope + '</th><th></th></tr>';

    for (let i = 0; i < graph.profile.data.length; i++) {
        if (i >= 1) dps = ((graph.profile.data[i][1] - graph.profile.data[i - 1][1]) / (graph.profile.data[i][0] - graph.profile.data[i - 1][0]) * 10) / 10;

        if (dps > 0) {
            slope = "up";
            color = "rgb(210,161,161)";
        } else if (dps < 0) {
            slope = "down";
            color = "rgb(120,146,176)";
            dps *= -1;
        } else if (dps === 0) {
            slope = "right";
            color = "rgb(176,177,178)";
        }

        let desiredSlopeId = 'desiredSlope-' + i;

        html += '<tr><td><h4>' + (i + 1) + '</h4></td>';
        html += '<td><input type="text" class="form-control" id="profiletable-0-' + i + '" value="' + timeProfileFormatter(graph.profile.data[i][0], true) + '" style="width: 60px" /></td>';
        html += '<td><input type="text" class="form-control" id="profiletable-1-' + i + '" value="' + graph.profile.data[i][1] + '" style="width: 60px" /></td>';
        html += '<td><input type="text" class="form-control" id="' + desiredSlopeId + '" value="" style="width: 60px" /></td>';
        html += `
        <td>
            <div class="input-group">
            <span class="input-group-addon" style="background: ${color}">
                <i class="fas fa-arrow-circle-${slope} fa-lg black-icon"></i>
            </span>
            <input type="text" class="form-control ds-input" readonly value="${formatDegreesPerTime(dps)}" style="width: 100px" />
            </div>
        </td>`;
        html += '<td>&nbsp;</td></tr>';
    }

    html += '</table></div>';

    document.getElementById('profile_table').innerHTML = html;

    // After the HTML is updated, attach blur event to each desiredSlope field
    for (let i = 0; i < graph.profile.data.length; i++) {
        let desiredSlopeField = document.getElementById('desiredSlope-' + i)

        if (desiredSlopeField) {
            // Attach blur event to the current desiredSlopeField
            desiredSlopeField.addEventListener('blur', function () {
                let desiredSlope = parseFloat(this.value);

                // Check if the desiredSlope is not a NaN
                if (!isNaN(desiredSlope) && desiredSlope !== 0) {
                    let prevTime = graph.profile.data[i - 1][0];
                    let prevTemp = graph.profile.data[i - 1][1];
                    let currTemp = graph.profile.data[i][1];
                    let endTime = calculateEndTime(desiredSlope, prevTime, prevTemp, currTemp);

                    let formattedEndTime = timeProfileFormatter(endTime, true)

                    // Set the endTime on UI
                    let element = document.getElementById('profiletable-0-' + i);
                    element.value = formattedEndTime;
                    // Dispatch the change event manually
                    element.dispatchEvent(new Event('change'));

                    // Reset the desiredSlope field after using it
                    this.value = "";
                }
            });
        }
    }

// Link table to graph
    let formControls = document.getElementsByClassName('form-control');
    Array.prototype.forEach.call(formControls, function (formControl) {
        formControl.addEventListener('change', function () {
            let id = this.id;

            // Ignoring desiredSlope field
            if (id.startsWith('desiredSlope')) {
                return;
            }

            let value = parseFloat(this.value);
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

function calculateEndTime(desiredSlope, prevTime, prevTemp, currTemp) {
    // Change in temperature
    let deltaTemp = currTemp - prevTemp;

    // Calculate time needed for the desired slope
    // Prevent division by zero when desiredSlope is zero by checking it first
    let deltaTime = desiredSlope !== 0 ? deltaTemp / desiredSlope : 0;

    // Calculate end time using previous time and calculated time
    // you may round as your need
    return prevTime + timeProfileFormatter(deltaTime, false);
}

function timeProfileFormatter(val, down) {
    let rval = val
    switch (timeScaleProfile) {
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
    return Math.round(rval * 100) / 100;
}


function formatDegreesPerTime(val) {
    let degreesPerTime = val;
    if (timeScaleSlope === "m") {
        degreesPerTime = val * 60;
    }
    if (timeScaleSlope === "h") {
        degreesPerTime = (val * 60) * 60;
    }
    return Math.round(degreesPerTime);
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

function enterMode(mode) {
    console.log(`Enter ${mode} Mode`);
    currentState = "EDIT";
    $('#status').slideUp();
    $('#edit').show();
    $('#profile_selector').hide();
    $('#btn_controls').hide();
    $('#progress').hide();
    $('#profile_table').slideDown();

    graph.profile.points.show = true;
    graph.profile.draggable = true;

    if (mode === "New") {
        $('#form_profile_name').val('').attr('placeholder', 'Please enter a name');
        graph.profile.data = [];
    } else if (mode === "Edit") {
        console.log(profiles);
        $('#form_profile_name').val(profiles[selectedProfile].name);
    }

    graph.plot = $.plot("#graph_container", [graph.profile, graph.live], getOptions());
    updateProfileTable();
}

function enterNewMode() {
    enterMode("New");
}

function enterEditMode() {
    enterMode("Edit");
}

function showControls() {
    currentState = IDLE;
    $('#edit').hide();
    $('#profile_selector').show();
    $('#btn_controls').show();
    $('#progress').show();
    $('#status').slideDown();
    $('#profile_table').slideUp();
    graph.profile.points.show = false;
    graph.profile.draggable = false;
    graph.plot = $.plot("#graph_container", [graph.profile, graph.live], getOptions());
}

function leaveEditMode() {
    selectedProfileName = $('#form_profile_name').val();
    showControls();
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
    switch (timeScaleProfile) {
        case "s":
            return 1;
        case "m":
            return 60;
        case "h":
            return 3600;
    }
}

const AXIS_FONT = {
    size: 14,
    lineHeight: 14,
    weight: "normal",
    family: "Digi",
    variant: "small-caps",
    color: "rgba(216, 211, 197, 0.85)"
};
const TICK_COLOR = 'rgba(216, 211, 197, 0.2)';
const GRID_COLOR = 'rgba(216, 211, 197, 0.55)';

function generateXAxis() {
    return {
        min: 0,
        tickColor: TICK_COLOR,
        tickFormatter: timeTickFormatter,
        tickSize: get_tick_size(),
        font: AXIS_FONT
    }
}


function generateYAxis() {
    return {
        min: 0,
        tickDecimals: 0,
        draggable: false,
        tickColor: TICK_COLOR,
        font: AXIS_FONT
    }
}


function getOptions() {
    return {
        series: {
            lines: {
                show: true
            },
            points: {
                show: true,
                radius: 5,
                symbol: "circle"
            },
            shadowSize: 3
        },
        xaxis: generateXAxis(),
        yaxis: generateYAxis(),
        grid: {
            color: GRID_COLOR,
            borderWidth: 1,
            labelMargin: 10,
            mouseActiveRadius: 50
        },
        legend: {
            show: false
        }
    };
}

function updateSelectedProfile(profileData) {
    if (profileData) {
        selectedProfileName = profileData.name;
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
    if (state !== RUNNING && state !== COMPLETE) {
        icon.innerHTML = '';
        text.innerHTML = '';
        progressBar.style.backgroundColor = '';
        return;
    }

    // Setting styles specific to RUNNING state
    if (state === RUNNING) {
        icon.innerHTML = isSimulation ? '🎛️' : '🔥';
        text.innerHTML = isSimulation ? 'Running Simulation' : 'Heating Kiln';
        text.style.color = isSimulation ? '#4aa3c4FF' : '#e70808';
        progressBar.style.backgroundColor = isSimulation ? '#4AA3C4' : '#e70808';
    }

    // Setting text for COMPLETE state
    if (state === COMPLETE) {
        text.innerHTML = isSimulation ? 'Simulation Complete' : 'Kiln Run Complete';
    }
}


function updateProfileSelector() {
    console.log('updateProfileSelector')
    let profileSelector = $('#e2');
    profileSelector.find('option').remove().end();

    let valid_profile_names = profiles.map(function (a) {
        return a.name;
    });

    if (valid_profile_names.length > 0 && $.inArray(selectedProfileName, valid_profile_names) === -1) {
        selectedProfile = 0;
        selectedProfileName = valid_profile_names[0];
    }

    profiles.forEach(function (profile, i) {
        profileSelector.append('<option value="' + i + '">' + profile.name + '</option>');
        if (profile.name === selectedProfileName) {
            selectedProfile = i;
            profileSelector.select2('val', i);
            updateProfile(i);
        }
    });
}


function initializeProfileSelector() {
    let profileSelector = $('#e2');

    // Initialize the profile selector with select2 plugin
    profileSelector.select2({
        placeholder: "Select Profile", allowClear: true, minimumResultsForSearch: -1
    });

    // Event handler for when a new profile is selected
    profileSelector.on("change", function (e) {
        updateProfile(e.val);
    });
}


$(document).ready(function () {

    // Initialize Socket.IO client
    let socket = io(`${window.location.protocol}//${window.location.hostname}:${window.location.port}`);

    initializeProfileSelector();


    // Handle connection open
    socket.on('connect', function () {
        console.log("Connected to server via Socket.IO");
        graph.live.data.length = 0; // Clear the history line

        console.log("Request Config Data")
        socket.emit('request_config'); // Request initial config on first connection
        socket.emit('request_backlog'); // Request initial backlog data on first connection
        socket.emit('request_profiles');
    });

    socket.on('oven_update', handleStatusUpdate);
    socket.on('backlog_data', handleBacklogData);
    socket.on('get_config', updateConfigDisplay);
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
    });

    // Bind the click events to the corresponding function
    $('#simulateButton').click(function () {
        runTaskSimulation();
    });

    $('#startRunButton').click(function () {
        runProfile();
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


    $('#btn_exit').click(function () {
        cancelProfileEdit();
    });

    function runProfile() {
        let cmd = {
            "cmd": "RUN", "profile": profiles[selectedProfile]
        };
        console.log("Run Profile")
        graph.live.data.length = 0;
        graph.plot = $.plot("#graph_container", [graph.profile, graph.live], getOptions());
        socket.emit('control', cmd); // Send command via Socket.IO
    }

    function runTaskSimulation() {
        let cmd = {
            "cmd": "SIMULATE", "profile": profiles[selectedProfile]
        };

        graph.live.data.length = 0;
        graph.plot = $.plot("#graph_container", [graph.profile, graph.live], getOptions());

        // Use Socket.IO to emit the command
        socket.emit('control', cmd);
    }

    function abortTask() {
        let cmd = {"cmd": "STOP"};
        socket.emit('control', cmd);
    }

    function handleStatusUpdate(statusData) {
        // console.log('handleStatusUpdate:' + JSON.stringify(statusData));

        // Update global state
        currentState = statusData.state;

        // Handle state change
        if (currentState !== lastState) {

            // Disable or enable profile selector, edit, and new profile button based on the state
            if (currentState !== IDLE) {
                $('#e2, #btn_edit, #btn_new').prop('disabled', true).addClass('disabled-button');
            } else {
                $('#e2, #btn_edit, #btn_new').prop('disabled', false).removeClass('disabled-button');
            }

            if (lastState === RUNNING && currentState !== RUNNING) {
                // Notify completion if the previous state was RUNNING
                notifyRunCompleted(statusData);
            }
            lastState = currentState;
        }

        let heatPercent = (parseFloat(statusData.heat) * 100).toFixed(0)
        $('#actTemp').html(parseFloat(statusData.temperature).toFixed(1));
        $('#percentHeat').html(heatPercent);


        // Update UI based on the current state
        if (currentState === RUNNING || currentState === COMPLETE || currentState === ABORTED) {
            // Update the graph with live data
            updateForNonIdleState(statusData);

        } else {
            updateForIdleState(statusData);
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

    function updateForNonIdleState(data) {
        $("#nav_start").hide();
        $("#nav_stop").show();

        updateRunIndicator(data.is_simulation, data.state); // Pass the isSimulation flag and state
        graph.live.data.push([data.time_stamp, data.temperature]);
        graph.plot = $.plot("#graph_container", [graph.profile, graph.live], getOptions());

        let timeDisplay;
        if (data.state === COMPLETE) {
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

    function updateForIdleState(data) {
        // Update UI for non-running state
        $("#nav_start").show();
        $("#nav_stop").hide();
        updateRunIndicator(data.is_simulation, data.state);
        $('#state').html('<p class="ds-text">' + currentState + '</p>');

        // Reset progress bar if idle
        if (currentState === IDLE) {
            updateProgress(0);
        }
    }

    function handleBacklogData(data) {
        console.log("handleBacklogData" + JSON.stringify(data))
        updateSelectedProfile(data.profile);
        updateGraphWithLogData(data.log);
    }

    function updateConfigDisplay(configData) {
        console.log('updateConfigDisplay')
        // Update temperature and timescale display based on received config
        tempScale = configData.temp_scale;
        timeScaleSlope = configData.time_scale_slope;
        timeScaleProfile = configData.time_scale_profile;
        kwh_rate = configData.kwh_rate;
        currency_type = configData.currency_type;

        tempScaleDisplay = tempScale === "c" ? "C" : "F";

        console.log("tempScale: ", configData.temp_scale,
            "\ntimeScaleSlope: ", configData.time_scale_slope,
            "\ntimeScaleProfile: ", configData.time_scale_profile,
            "\nkwh_rate: ", configData.kwh_rate,
            "\ncurrency_type: ", configData.currency_type,
            "\ntempScaleDisplay: ", tempScale === "c" ? "C" : "F");

        $('#act_temp_scale').html('º' + tempScaleDisplay);
        $('#target_temp_scale').html('º' + tempScaleDisplay);

        switch (timeScaleProfile) {
            case "s":
                timeScaleLong = "Seconds";
                break;
            case "m":
                timeScaleLong = "Minutes";
                break;
            case "h":
                timeScaleLong = "Hours";
                break;
        }
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


    function cancelProfileEdit() {
        socket.emit('request_profiles');
        leaveEditMode();
    }

    function saveProfile() {
        name = $('#form_profile_name').val();

        if (!name.trim()) {
            displayBootstrapGrowl("Profile name cannot be blank.", 'error', 3);
            return;
        }

        let rawdata = graph.plot.getData()[0].data
        let data = [];
        let last = -1;

        for (let i = 0; i < rawdata.length; i++) {
            if (rawdata[i][0] > last) {
                data.push([rawdata[i][0], rawdata[i][1]]);
            } else {
                displayBootstrapGrowl("<span class=\"glyphicon glyphicon-exclamation-sign\"></span> <b>ERROR 88:</b><br/>An oven is not a time-machine", 'error', 3)
                return false;
            }
            last = rawdata[i][0];
        }

        let profile = {"type": "profile", "data": data, "name": name}
        let put = {"cmd": "PUT", "profile": profile}

        // This call will also push profiles after save.
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
    }

    function deleteProfile() {

        console.log("Delete profile:" + selectedProfileName);

        socket.emit('delete_profile', selectedProfileName);

        selectedProfileName = profiles[0].name;
        $('#e2').select2('val', 0);

        showControls()
    }
});
