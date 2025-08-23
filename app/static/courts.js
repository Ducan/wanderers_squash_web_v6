/*
Developer Notes:
- Handles dynamic functionality for the dates_container and courts_container.
- Includes dynamic court descriptions, legends, and periods logic.
- Refactored to separate booking logic into bookings.js for maintainability.
*/

// Global error handler to reload the page once if an error is detected in the courts module
(function() {
    // Check if a previous reload happened due to an error.
    if (sessionStorage.getItem("hasReloadedDueToError") === "true") {
        console.log("Page reloaded previously due to an error in courts.js.");
        // Optionally, clear the flag if you only want to log once.
        // sessionStorage.removeItem("hasReloadedDueToError");
    }

    window.onerror = function(message, source, lineno, colno, error) {
        // Check for errors coming from courts.js and ensure we haven't reloaded yet.
        if (source && source.indexOf("courts.js") !== -1 && sessionStorage.getItem("hasReloadedDueToError") !== "true") {
            console.error("Error detected in courts.js. Preparing to reload...", {
                message: message,
                source: source,
                lineno: lineno,
                colno: colno,
                error: error
            });
            // Set a flag so we only reload once.
            sessionStorage.setItem("hasReloadedDueToError", "true");
            console.log("Page is reloading due to error in courts.js.");
            window.location.reload();
        }
        // Allow default error logging
        return false;
    };
})();



// Use var for global variables to prevent re-declaration errors
var currentSelectedDate = null;
var lastSelectedDate = null; // Track the last selected date to prevent duplicate calls

// Expose the function globally - Relevant to the dates container.
window.getSelectedDate = getSelectedDate;

// Global map to store court descriptions and IDs
var courtIdMap = {};

/**
 * Utility Functions
 */

// Base URL for all API calls
if (typeof BASE_URL === 'undefined') {
    var BASE_URL = '/main/courts';
}

// Format date to "dd/MM/yyyy"
function reformatDateToDdMmYyyy(date) {
    const [year, month, day] = date.split("-");
    return `${day}/${month}/${year}`;
}

// Format time to "HH:MM" 24-hour format
function formatTimeTo24Hour(time) {
    const [hours, minutes] = time.split(":").map(Number);
    return `${hours.toString().padStart(2, "0")}:${minutes.toString().padStart(2, "0")}`;
}

// Format date for display in the date block
function formatDate(date) {
    const day = date.getDate();
    const weekday = date.toLocaleDateString("en-US", { weekday: "short" });
    const month = date.toLocaleDateString("en-US", { month: "short" });
    const year = date.toLocaleDateString("en-US", { year: "2-digit" });
    return `${weekday} ${day} ${month} '${year}`;
}
// Utility to get the selected date from dates_container
function getSelectedDate() {
    const selectedDateBlock = document.querySelector(".date-block.selected");
    return selectedDateBlock ? selectedDateBlock.dataset.date : null;
}

/**
 * Populate the dates container with selectable date blocks.
 */
function populateDatesContainer(datesContainer, today) {
    datesContainer.innerHTML = "";

    for (let i = 0; i <= 7; i++) {
        const date = new Date(today);
        date.setDate(today.getDate() + i);

        const dateBlock = document.createElement("div");
        dateBlock.className = "date-block";
        dateBlock.textContent = formatDate(date);
        // Store the date using local timezone to avoid UTC offset issues
        // Use en-CA locale to ensure YYYY-MM-DD format
        dateBlock.dataset.date = date.toLocaleDateString("en-CA");

        if (i === 0) {
            dateBlock.classList.add("selected");
            currentSelectedDate = dateBlock.dataset.date;
        }

        dateBlock.tabIndex = 0;
        dateBlock.addEventListener("click", handleDateClick);
        datesContainer.appendChild(dateBlock);
    }
}

function handleDateClick(event) {
    document.querySelectorAll(".date-block").forEach(block => block.classList.remove("selected"));
    event.target.classList.add("selected");

    currentSelectedDate = event.target.dataset.date; // Update selected date
    console.log("Date selected:", currentSelectedDate);

    refreshCourtsData(currentSelectedDate); // Fetch and refresh data for the new date
}


/**
 * Populate the legends_container with periods, Waiting List, and their colors.
 * Synchronize Time Slot Legend colors with the periods_column.
 * Includes default costs if the backend fails to fetch data.
 */
function populateLegendsContainer(periods, defaultCosts = {}) {
    const legendsContainer = document.getElementById("legends_container");
    legendsContainer.innerHTML = ""; // Clear existing content

    if (!legendsContainer) {
        console.error("Legends container not found!");
        return;
    }

    // Fetch the user credit from the session (S_Credit)
    const userCredit = window.user?.credit || 0;

    // Create and append the Lights Credit display
    const creditDisplay = document.createElement("div");
    creditDisplay.textContent = `Lights Credit: N$${parseFloat(userCredit).toFixed(2)}`;
    creditDisplay.style.fontWeight = "bold";
    creditDisplay.style.marginRight = "10px";
    legendsContainer.appendChild(creditDisplay);

    // Add a separator between Lights Credit and Time Slot Legend
    const separator1 = document.createElement("span");
    separator1.textContent = " | ";
    separator1.style.margin = "0 10px";
    legendsContainer.appendChild(separator1);

    // Add the Time Slot Legend label
    const legendsLabel = document.createElement("span");
    legendsLabel.textContent = "Time Slot Legend:";
    legendsLabel.style.fontWeight = "bold";
    legendsLabel.style.marginRight = "10px";
    legendsContainer.appendChild(legendsLabel);

    // Add each period as a legend item synchronized with the periods_column
    periods.forEach((period) => {
        const legendItem = document.createElement("div");
        legendItem.className = "legend-item";

        // Use default costs if backend data is unavailable
        const totalCost = defaultCosts[period.description] || "N/A";

        // Use the same color logic as periods_column
        legendItem.style.backgroundColor = period.color; // Sync color with periods_column
        legendItem.style.color = "#000"; // Ensure readable text
        legendItem.style.padding = "5px 10px";
        legendItem.style.margin = "5px";
        legendItem.style.borderRadius = "5px";
        legendItem.innerHTML = `${period.description} <span style="font-weight: 600;">N$${totalCost}</span>`;

        legendsContainer.appendChild(legendItem);
    });

    // Add a separator between Time Slot Legend and Waiting List
    const separator2 = document.createElement("span");
    separator2.textContent = " | ";
    separator2.style.margin = "0 10px";
    legendsContainer.appendChild(separator2);

    // Add the Waiting List label
    const waitingListLabel = document.createElement("span");
    waitingListLabel.textContent = "Waiting List Availability";
    waitingListLabel.style.fontWeight = "bold";
    waitingListLabel.style.marginRight = "10px";
    legendsContainer.appendChild(waitingListLabel);

    // Dynamically fetch the color of the selected date block
    const selectedDateBlock = document.querySelector(".date-block.selected");
    const selectedColor = window.getComputedStyle(selectedDateBlock).backgroundColor || "#000000";

    // Add a block with a dynamic color for Waiting List
    const waitingListBlock = document.createElement("div");
    waitingListBlock.className = "legend-item";
    waitingListBlock.style.backgroundColor = selectedColor; // Use dynamic color from selected date
    waitingListBlock.style.color = "#FFFFFF"; // Text in white
    waitingListBlock.style.display = "flex";
    waitingListBlock.style.justifyContent = "center";
    waitingListBlock.style.alignItems = "center";
    waitingListBlock.style.padding = "5px 10px";
    waitingListBlock.style.borderRadius = "5px";
    waitingListBlock.textContent = "Select Time";
    legendsContainer.appendChild(waitingListBlock);
}

/**
 * Fetch and update the Time Slot Legend with costs for 45-minute bookings.
 */
function updateTimeSlotLegend(periods) {
    fetch('/financials/court_booking_costs')
        .then((response) => {
            if (!response.ok) {
                throw new Error(`Error fetching court booking costs: ${response.statusText}`);
            }
            return response.json();
        })
        .then((data) => {
            const defaultCosts = {};
            if (data.status === "success" && Array.isArray(data.data)) {
                data.data.forEach((period) => {
                    defaultCosts[period.description] = period.total_cost;
                });
            }
            populateLegendsContainer(periods, defaultCosts);
        })
        .catch((error) => {
            console.error("Error updating Time Slot Legend:", error.message);
            // Populate legends with default costs if API fails
            populateLegendsContainer(periods);
        });
}

/**
 * Populate the periods_container with periods aligned to the time slots.
 * Displays only the first letter of the period description in the periods column.
 * Ensures booking cells retain "Available" by default and period IDs are aligned.
 * Dynamically initializes hover and click functionality for peak periods.
 */
function populatePeriodsContainer(periods) {
    const tableBody = document.getElementById("time_slots_table_body");
    const rows = tableBody.querySelectorAll("tr");

    rows.forEach((row, rowIndex) => {
        if (!periods[rowIndex]) {
            console.warn(`No period data for row index ${rowIndex}`);
            return;
        }

        // Iterate over courts dynamically
        const courts = ["court_1", "court_2", "court_3", "court_4"];
        const periodData = periods[rowIndex];

        courts.forEach((courtKey, courtIndex) => {
            const cellIndex = courtIndex + 2; // Booking cells start from index 2 (after time and periods columns)
            const bookingCell = row.children[cellIndex]; // Adjust for time cell and periods column
            const periodCell = row.children[1]; // Periods column is always at index 1

            // Handle booking cells
            if (!periodData[courtKey]) {
                bookingCell.textContent = "Available"; // Default to "Available"
                bookingCell.style.backgroundColor = "#FFFFFF"; // Reset to default white background
                bookingCell.style.color = "#000000"; // Reset to default black text
                return;
            }

            const periodDataForCourt = periodData[courtKey];
            const periodDescription = periodDataForCourt.description || "Unknown";
            const periodColor = periodDataForCourt.color || "#FFFFFF";
            const periodId = periodDataForCourt.period_id || "N/A"; // Default to "N/A" if undefined

            // Ensure "Available" remains the default for unbooked cells
            if (!bookingCell.classList.contains("booked")) {
                bookingCell.textContent = "Available"; // Default to "Available"
                bookingCell.style.backgroundColor = "#FFFFFF"; // Default white background
                bookingCell.style.color = "#000000"; // Default black text
            }

            // Handle periods column separately
            if (periodCell) {
                const periodAbbreviation = periodDescription.charAt(0).toUpperCase(); // First letter of the period description
                periodCell.textContent = periodAbbreviation; // Display the period abbreviation
                periodCell.style.backgroundColor = periodColor; // Apply the period's background color
                periodCell.setAttribute("data-period-id", periodId); // Add period ID as a data attribute
            }

            console.log(
             //   `Row ${rowIndex}, Court ${courtIndex + 1}: Period ID=${periodId}, Description=${periodDescription}`
            );
        });
    });

    // Dynamically initialize hover and click functionality for peak periods
    initializePeakPeriodHoverAndClick();
}


/**
 * Refresh legends data for the selected date.
 */
function refreshLegendsData() {
    fetch(`/periods/get_all_periods`)
        .then((response) => {
            if (!response.ok) {
                throw new Error(`Error fetching periods: ${response.statusText}`);
            }
            return response.json();
        })
        .then((data) => {
            if (data && data.data && Array.isArray(data.data)) {
                updateTimeSlotLegend(data.data);
            } else {
                console.warn("No period data available.");
                const legendsContainer = document.getElementById("legends_container");
                if (legendsContainer) {
                    legendsContainer.innerHTML = "<div>No period data available.</div>";
                }
            }
        })
        .catch((error) => {
            console.error(`Error loading legends: ${error.message}`);
            const legendsContainer = document.getElementById("legends_container");
            if (legendsContainer) {
                legendsContainer.innerHTML = `<div>Error loading legends: ${error.message}</div>`;
            }
        });
}


/**
 * Create a table row with placeholders for time, periods, and booking cells.
 */
function createRowWithPlaceholders(slot) {
    const formattedTime = formatTimeTo24Hour(slot.time);
    const row = document.createElement("tr");

    row.dataset.slotId = slot.slot_id;
    row.dataset.slotKey = slot.slot_key;

    const timeCell = document.createElement("td");
    timeCell.className = "time-cell";
    timeCell.textContent = formattedTime;
    row.appendChild(timeCell);

    const periodCell = document.createElement("td");
    periodCell.className = "period-cell";
    row.appendChild(periodCell);

    const headerCells = document.querySelectorAll("#courts_container table thead tr th.court-description");
    headerCells.forEach((headerCell) => {
        const bookingCell = document.createElement("td");
        bookingCell.className = "booking-cell available";
        bookingCell.textContent = "Available";
        bookingCell.tabIndex = 0;
        bookingCell.dataset.courtId = headerCell.dataset.courtId;
        row.appendChild(bookingCell);
    });

    return row;
}

/**
 * Fetch courts with descriptions and IDs.
 */
function fetchCourtsWithIds() {
    return fetch(`${BASE_URL}/descriptions`)
        .then((response) => {
            if (!response.ok) {
                throw new Error(`Error fetching courts: ${response.statusText}`);
            }
            return response.json();
        })
        .then((data) => {
            const courts = data.courts || [];
            courtIdMap = courts.reduce((map, court) => {
                map[court.description] = court.number; // Map description to CourtNo
                return map;
            }, {});
            updateCourtHeaders(courts);
        })
        .catch((error) => {
            console.error("Error fetching courts:", error);
        });
}

/**
 * Updates court headers dynamically based on court descriptions and IDs.
 */
function updateCourtHeaders(courts) {
    const headerRow = document.querySelector("#courts_container table thead tr");
    const descriptionCells = headerRow.querySelectorAll("th.court-description");

    courts.forEach((court, index) => {
        if (descriptionCells[index]) {
            descriptionCells[index].textContent = court.description;
            descriptionCells[index].dataset.courtId = court.number; // Attach CourtNo
        }
    });
}

/**
 * Align colors for peak period time slots in the time column.
 * Sets the time column text color to white for peak periods.
 * Ensures booking cells retain default styles unless booked.
 */
function alignPeakPeriodColors() {
    const selectedDateBlock = document.querySelector(".date-block.selected");
    if (!selectedDateBlock) return;

    const selectedColor = window.getComputedStyle(selectedDateBlock).backgroundColor;
    const periodCells = document.querySelectorAll(".period-cell");

    periodCells.forEach((cell) => {
        const periodAbbreviation = cell.textContent.trim().toUpperCase(); // Check single-letter description
        if (periodAbbreviation === "P") { // 'P' represents "Peak"
            const row = cell.closest("tr");
            const timeCell = row.querySelector(".time-cell"); // Find the corresponding time cell

            if (timeCell) {
                // Apply color to the time column for peak periods
                timeCell.style.backgroundColor = selectedColor;
                timeCell.style.color = "#FFFFFF"; // Set the text color to white
            }

            // Ensure booking cells in the row are not affected until booked
            const bookingCells = row.querySelectorAll(".booking-cell");
            bookingCells.forEach((bookingCell) => {
                if (!bookingCell.classList.contains("booked")) {
                    bookingCell.style.backgroundColor = "#FFFFFF"; // Default white background
                    bookingCell.style.color = "#000000"; // Default black text
                }
            });
        }
    });
}


/**
 * Refresh courts and periods data for the selected date.
 */
function refreshCourtsData(selectedDate, force = false) {
    if (selectedDate === lastSelectedDate && !force) {
        console.log("Selected date has not changed. Skipping refresh...");
        return;
    }
    lastSelectedDate = selectedDate;

    const formattedDate = reformatDateToDdMmYyyy(selectedDate); // Format the date to dd/MM/yyyy
    const tableBody = document.getElementById("time_slots_table_body");
    tableBody.innerHTML = ""; // Clear the table body for new data
    if (window.resetBookingsBinding) {
        window.resetBookingsBinding();
    }

    // Fetch time slots for the selected date
    fetch(`${BASE_URL}/time_slots?date=${formattedDate}`)
        .then((response) => response.json())
        .then((data) => {
            const timeSlots = data.time_slots || [];
            timeSlots.forEach((slot) => {
                const row = createRowWithPlaceholders(slot); // Create table rows for time slots
                tableBody.appendChild(row);
            });

            // Fetch periods for the selected date after populating time slots
            return fetch(`${BASE_URL}/periods_for_day?date=${formattedDate}`);
        })
        .then((response) => response.json())
        .then((periods) => {
            console.log("Periods Data Received:", periods); // Debugging line
            populatePeriodsContainer(periods); // Populate the periods column in the table
            alignPeakPeriodColors(); // Align colors for peak period time slots
            refreshBookingsData(selectedDate); // Refresh bookings for the selected date
            if (window.initializeBookings) {
                window.initializeBookings();
            }
        })
        .catch((error) => {
            console.error("Error fetching courts data:", error);
        });
}

/**
 * Initialize courts functionality
 * - Populates dates_container and legends_container.
 * - Sets up data refresh logic for the courts.
 */
function initializeCourts() {
    console.log("Initializing courts...");
    lastSelectedDate = null; // Ensure refreshCourtsData runs on page load
    const datesContainer = document.getElementById("dates_container");
    if (!datesContainer) {
        console.error("dates_container not found!");
        return;
    }

    const today = new Date();

    // Fetch session info and update window.user
    fetch('/main/session_info')
        .then(response => response.json())
        .then(data => {
            window.user = data; // Store session data globally
            updateLightsCredit(data.credit); // Ensure legend reflects latest credit
            console.log("[INFO] Session information loaded:", window.user);

            // Fetch courts and update headers
            fetchCourtsWithIds()
                .then(() => {
                    populateDatesContainer(datesContainer, today); // Populate dates
                    refreshLegendsData(); // Refresh legends and update legend costs
                    refreshCourtsData(currentSelectedDate, true); // Force data refresh on load
                })
                .catch((error) => {
                    console.error("Error fetching courts data during initialization:", error);
                });
        })
        .catch(error => {
            console.error("Error fetching session data:", error);
        });

    console.log("Courts initialization complete.");
}



// Initialization code
document.addEventListener("DOMContentLoaded", initializeCourts);

// Expose the initializeCourts function globally
window.initializeCourts = initializeCourts;
