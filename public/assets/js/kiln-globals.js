// globals.js

// Global Variables
let state = "----";
let state_last = "";
let graph = {profile: {}, live: {}};
let profiles = [];
let selected_profile = 0;
let selected_profile_name = "";
let temp_scale = ""; // F or C
let time_scale_slope = "s";
let time_scale_profile = "s";
let time_scale_long = "Seconds";
let temp_scale_display = "";
let kwh_rate = 0.0;
let currency_type = "";

// Utility Functions
function timeProfileFormatter(val, down) {
    // Function to format the profile time
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
    // Function to format DPS (Degrees Per Second?)
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
    // Function to calculate the hazard temperature
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

function get_tick_size() {
    // Function to get tick size

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
    // Function to get graph options

    return {

        series: {
            lines: {
                show: true
            },

            points: {
                show: true, radius: 5, symbol: "circle"
            },

            shadowSize: 3

        },

        xaxis: {
            min: 0,
            tickColor: 'rgba(216, 211, 197, 0.2)',
            tickFormatter: timeTickFormatter,
            tickSize: get_tick_size(),
            font: {
                size: 14,
                lineHeight: 14,
                weight: "normal",
                family: "Digi",
                variant: "small-caps",
                color: "rgba(216, 211, 197, 0.85)"
            }
        },

        yaxis: {
            min: 0, tickDecimals: 0, draggable: false, tickColor: 'rgba(216, 211, 197, 0.2)', font: {
                size: 14,
                lineHeight: 14,
                weight: "normal",
                family: "Digi",
                variant: "small-caps",
                color: "rgba(216, 211, 197, 0.85)"
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

// Add other global functions or variables as needed
