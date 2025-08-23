/**
 * Utility Functions
 */

// Track the current table body element that has the booking click listener
let boundTableBody = null;

// Shared click handler so it can be attached/detached
function tableBodyClickListener(event) {
    const cell = event.target.closest(".booking-cell");
    if (cell) {
        handleSlotClick(cell);
    }
}

/**
 * Format the selected date and time into StartTime1 format.
 * @param {string} date - The date in "yyyy-mm-dd" format.
 * @param {string} time - The time in "HH:MM" format.
 * @returns {string} - The formatted StartTime1 value in "dd/mm/yyyy HH:MM:SS".
 */
function formatStartTime1(date, time) {
    const [year, month, day] = date.split("-");
    const formattedDate = `${day}/${month}/${year}`; // Convert to "dd/mm/yyyy"
    const formattedTime = `${time}:00`; // Append "00" for seconds
    return `${formattedDate} ${formattedTime}`;
}

/**
 * Dynamically link the bookings functionality to the dates_container.
 * Logs the date range loaded in the format "dd/mm/yyyy - dd/mm/yyyy".
 * If a single date is selected, logs the selected date as "dd/mm/yyyy".
 */
function linkBookingsToDatesContainer() {
    console.log("Linking to dates_container..."); // Debug: Function entry log

    const datesContainer = document.getElementById("dates_container");
    if (!datesContainer) {
        console.error("dates_container not found!");
        return;
    }

    // Collect all date blocks within the dates_container
    const dateBlocks = datesContainer.querySelectorAll(".date-block");

    if (dateBlocks.length === 0) {
        console.error("No date blocks found in dates_container!");
        return;
    }

    let dateRange = [];
    dateBlocks.forEach((block, index) => {
        const blockDate = block.dataset.date; // Date in "yyyy-mm-dd" format
        const formattedDate = reformatDateToDdMmYyyy(blockDate); // Convert to "dd/mm/yyyy"
        dateRange.push(formattedDate);
    });

    // Check if a single date or a range of dates is loaded
    if (dateRange.length === 1) {
        console.log(`Loaded single date: ${dateRange[0]}`); // Single date case
    } else {
        console.log(`Date range loaded: ${dateRange[0]} - ${dateRange[dateRange.length - 1]}`); // Range case
    }
}

/**
 * Utility to reformat date to "dd/mm/yyyy" format.
 * @param {string} date - The date in "yyyy-mm-dd" format.
 * @returns {string} - The date in "dd/mm/yyyy" format.
 */
function reformatDateToDdMmYyyy(date) {
    const [year, month, day] = date.split("-");
    return `${day}/${month}/${year}`;
}

/**
 * Duplicate booking safeguard utilities.
 * Store the last booking payload and timestamp in sessionStorage to avoid
 * rapid duplicate submissions.
 */
const LAST_BOOKING_KEY = "lastBookingPayload";
const DUPLICATE_INTERVAL_MS = 5000; // 5 seconds

function storeLastBooking(payload) {
    sessionStorage.setItem(
        LAST_BOOKING_KEY,
        JSON.stringify({ payload, timestamp: Date.now() })
    );
}

function isRecentDuplicate(payload) {
    const stored = sessionStorage.getItem(LAST_BOOKING_KEY);
    if (!stored) return false;
    try {
        const { payload: lastPayload, timestamp } = JSON.parse(stored);
        const isSame = JSON.stringify(lastPayload) === JSON.stringify(payload);
        const isRecent = Date.now() - timestamp < DUPLICATE_INTERVAL_MS;
        return isSame && isRecent;
    } catch (error) {
        return false;
    }
}

function clearLastBooking() {
    sessionStorage.removeItem(LAST_BOOKING_KEY);
}

// Reset the safeguard when navigating away from the page.
window.addEventListener("beforeunload", clearLastBooking);
window.addEventListener("pagehide", clearLastBooking);

async function checkBookingLimits(selectedDate, periodId, onSuccess) {
    try {
        // Fetch daily booking limits
        const dailyResponse = await fetch(`/bookings/booking_daily_limits?date=${reformatDateToDdMmYyyy(selectedDate)}`);
        const dailyData = await dailyResponse.json();

        // Check if the specific period's daily limit is reached
        const dailyLimit = dailyData.limits.find(limit => limit.period_id === parseInt(periodId));
        if (dailyLimit && dailyLimit.bookings_count >= dailyLimit.limit) {
            showLimitsPopup({
                status: "error",
                message: "Daily booking limit reached!",
                limits: dailyData.limits, // Show all daily limits
            });
            return false; // Prevent booking
        }

        // Calculate start_date (Monday) and end_date (Sunday) for the week of the selected date
        const date = new Date(selectedDate);
        const dayOfWeek = date.getDay(); // 0 (Sunday) to 6 (Saturday)
        const monday = new Date(date);
        monday.setDate(date.getDate() - dayOfWeek + (dayOfWeek === 0 ? -6 : 1)); // Adjust for Monday
        const sunday = new Date(monday);
        sunday.setDate(monday.getDate() + 6); // Add 6 days to get Sunday

        const startDate = reformatDateToDdMmYyyy(monday.toISOString().split("T")[0]);
        const endDate = reformatDateToDdMmYyyy(sunday.toISOString().split("T")[0]);

        // Fetch weekly booking limits
        const weeklyResponse = await fetch(
            `/bookings/booking_weekly_limits?start_date=${startDate}&end_date=${endDate}`
        );
        const weeklyData = await weeklyResponse.json();

        // Check if the specific period's weekly limit is reached
        const weeklyLimit = weeklyData.limits.find(limit => limit.period_id === parseInt(periodId));
        if (weeklyLimit && weeklyLimit.bookings_count >= weeklyLimit.limit) {
            showLimitsPopup({
                status: "error",
                message: "Weekly booking limit reached!",
                limits: weeklyData.limits, // Show all weekly limits
            });
            return false; // Prevent booking
        }

        // Proceed if limits are not exceeded
        onSuccess(dailyData.limits, weeklyData.limits);
        return true; // Allow booking
    } catch (error) {
        console.error("Error checking booking limits:", error);
        showLimitsPopup({
            status: "error",
            message: "Failed to check booking limits. Please try again later.",
        });
        return false; // Prevent booking on error
    }
}


/**
 * Booking code processes
 */

/**
 * Populate the booking cells with the booking data.
 * Updates the booking cells with the player names from the database and aligns their color to the period color.
 * Displays all bookings but marks past available slots as "Unavailable".
 * @param {Array} bookings - The array of booking data fetched from the backend.
 */
function populateBookingCells(bookings) {
    const tableBody = document.getElementById("time_slots_table_body");
    const rows = tableBody.querySelectorAll("tr");

    bookings.forEach((booking) => {
        const { time, players } = booking; // Each booking has a time and players array
        const formattedTime = formatTimeTo24Hour(time); // Ensure time is formatted consistently

        // Find the corresponding row for the booking time
        const row = Array.from(rows).find(
            (row) => row.querySelector(".time-cell")?.textContent === formattedTime
        );

        if (!row) {
            console.warn(`No matching row found for time: ${formattedTime}`);
            return; // Skip if no matching row is found
        }

        // Extract the period ID from the period column
        const periodCell = row.querySelector(".period-cell");
        const periodId = periodCell ? parseInt(periodCell.getAttribute("data-period-id"), 10) : null;

        if (!periodId) {
            console.error(`Period ID not found for row with time: ${formattedTime}`);
            return; // Skip if no period ID
        }

        // console.log(`Row Time: ${formattedTime}, Period ID: ${periodId}`); // Debugging

        // Populate booking cells for this row
        const bookingCells = row.querySelectorAll(".booking-cell");
        players.forEach((player, index) => {
            if (bookingCells[index]) {
                const bookingCell = bookingCells[index];

                bookingCell.textContent = player || "Available";
                bookingCell.classList.toggle("booked", !!player);

                // Dynamically align the cell color with the period's color
                const periodColor = periodCell.style.backgroundColor || "#FFFFFF"; // Default white
                bookingCell.style.backgroundColor = player ? periodColor : "#FFFFFF";
                bookingCell.style.color = player ? "#000000" : "#000000";

                // Store period ID in the booking cell for alignment during interactions
                bookingCell.setAttribute("data-period-id", periodId);

                // Disable past available slots
                const currentTime = new Date();
                const bookingDateTime = new Date(`${getSelectedDate()}T${formattedTime}:00`);
                if (!player && bookingDateTime < currentTime) {
                    bookingCell.textContent = "Unavailable";
                    bookingCell.classList.add("past-unavailable");
                    bookingCell.style.opacity = 0.5;
                }
            }
        });
    });
}

/**
 * Handles slot clicks for booking or cancellation, with booking limits enforcement.
 * @param {HTMLElement} cell - The clicked booking cell.
 */
function handleSlotClick(cell) {
    const row = cell.parentElement;
    const timeCell = row.querySelector(".time-cell");
    const selectedTime = timeCell.textContent; // e.g., "08:00"
    const slotId = row.dataset.slotId;

    const selectedDate = getSelectedDate(); // Get the selected date from dates_container

    if (!selectedDate) {
        alert("No date selected. Please select a date.");
        return;
    }

    // Retrieve the period ID from the period cell
    const periodCell = row.querySelector(".period-cell");
    const periodId = periodCell ? periodCell.getAttribute("data-period-id") : null;

    if (!periodId) {
        alert("Period ID could not be determined for this booking.");
        return;
    }

    // Check if the booking is for a past time
    const currentTime = new Date();
    const bookingDateTime = new Date(`${selectedDate}T${selectedTime}:00`); // Convert to ISO format

    if (bookingDateTime < currentTime) {
        alert("Cannot book for a past time. Please select a present or future time.");
        return;
    }


    // Always fetch the latest user info to ensure up-to-date Lights Credit
    fetch("/bookings/get_user_info", { method: "GET", credentials: "same-origin" })
        .then((response) => {
            if (!response.ok) throw new Error(`Error: ${response.status} ${response.statusText}`);
            return response.json();
        })
        .then((userInfo) => {
            window.user = userInfo; // Keep global user data in sync
            updateLightsCredit(userInfo.credit); // Update UI with the latest credit
            if (!userInfo.first_name || !userInfo.last_name) {
                throw new Error("Incomplete user information.");
            }

            const userName = `${userInfo.first_name.charAt(0)} ${userInfo.last_name}`;
            const playerNo = userInfo.Mem_No || userInfo.member_no;

            // Fetch Lights Credit from user data
            const lightsCredit = parseFloat(userInfo.credit || "0");
            if (lightsCredit <= 0) {
                alert("Booking not allowed. Insufficient Lights Credit (0.00 or below).");
                return;
            }

            if (cell.textContent === userName) {
                // User clicks on their own booking -> Allow deletion
                deleteBookingFromServer(selectedDate, slotId, playerNo, row, cell, () => {
                    // Reload booking counts after deletion
                    refreshBookingLimits(selectedDate);
                });
            } else if (cell.textContent === "Available") {
                // New booking -> Check limits for the specific period before proceeding
                checkBookingLimits(selectedDate, periodId, (dailyLimits, weeklyLimits) => {
                    // Proceed with the booking
                    cell.textContent = userName;
                    cell.classList.remove("available");
                    cell.classList.add("booked");

                    if (periodCell) {
                        cell.style.backgroundColor = periodCell.style.backgroundColor;
                    }

                    writeBookingToServer(slotId, selectedDate, userInfo, row, cell, () => {
                        // Reload booking counts after a successful booking
                        refreshBookingLimits(selectedDate);
                    });
                });
            } else {
                alert("This slot is already booked by another user.");
            }
        })
        .catch((error) => {
            console.error("Error fetching user information:", error);
            alert("Unable to retrieve user information. Please try again.");
        });
}






/**
 * Delete Internet bookings.
 */
function deleteBookingFromServer(selectedDate, slotId, playerNo, row, clickedCell, onSuccess) {
    try {
        const cellIndex = clickedCell.cellIndex;
        const headerRow = document.querySelector("#courts_container table thead tr");
        const headerCell = headerRow ? headerRow.children[cellIndex] : null;
        const courtId = headerCell ? parseInt(headerCell.getAttribute("data-court-id"), 10) : NaN;

        if (isNaN(courtId)) {
            showDebugPopup({
                status: "error",
                message: "Court ID not found for the selected cell.",
                debug: { clickedCell, cellIndex },
            });
            return;
        }

        const payload = {
            date_container: selectedDate,
            slot_id: slotId,
            player_no_column: `PlayerNo_${courtId}`,
            player_no: playerNo,
            selected_court: courtId,
        };

        // Show the popup with additional debug information when booking was deleted
        // showDebugPopup({
        //    status: "success",
        //    message: "Data prepared for booking deletion.",
        //    data: payload,
       // });

        // Send POST request to delete booking on the server
        fetch("/bookings/delete", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        })
            .then((response) => response.json())
            .then((data) => {
                console.log("[DEBUG] Cancellation response:", data);
                if (data.error) {
                    console.error("[ERROR] Backend error:", data.error);
                } else {
                    updateLightsCredit(data.updated_credit);
                    clickedCell.textContent = "Available";
                    clickedCell.classList.remove("booked");
                    clickedCell.classList.add("available");
                    clickedCell.style.backgroundColor = "#FFFFFF"; // Reset to default color
                    if (typeof onSuccess === "function") {
                        onSuccess();
                    }
                }
            })
            .catch((error) => {
                console.error("[ERROR] Error deleting booking:", error);
                alert("Error deleting booking. Please check the console for more details.");
            });
    } catch (error) {
        showDebugPopup({
            status: "error",
            message: "Unexpected error during data preparation for booking deletion.",
            debug: { error },
        });
    }
}


/**
 * Dynamically update the Lights Credit in legends_container.
 * @param {number} updatedCredit - The updated S_Credit value.
 */
function updateLightsCredit(updatedCredit) {
    const legendsContainer = document.getElementById("legends_container");
    if (!legendsContainer) {
        console.error("Legends container not found!");
        return;
    }

    // Keep the global user object's credit in sync
    if (window.user) {
        window.user.credit = updatedCredit;
    } else {
        window.user = { credit: updatedCredit };
    }

    const creditDisplay = legendsContainer.querySelector(":scope > div:first-child");
    if (creditDisplay) {
        creditDisplay.textContent = `Lights Credit: N$ ${parseFloat(updatedCredit).toFixed(2)}`;
    } else {
        // Add a new Lights Credit display if not present
        const newCreditDisplay = document.createElement("div");
        newCreditDisplay.textContent = `Lights Credit: N$ ${parseFloat(updatedCredit).toFixed(2)}`;
        newCreditDisplay.style.fontWeight = "bold";
        legendsContainer.prepend(newCreditDisplay);
    }
}

/**
 * Refresh booking limits for the logged-in player.
 * Fetches the latest daily and weekly booking limits from the server.
 * @param {string} selectedDate - The selected date in dd/MM/yyyy format.
 */
function refreshBookingLimits(selectedDate) {
    fetch(`/bookings/get_booking_limitations`, { method: "GET", credentials: "same-origin" })
        .then((response) => {
            if (!response.ok) throw new Error(`Error fetching booking limits: ${response.statusText}`);
            return response.json();
        })
        .then((data) => {
            console.log("[DEBUG] Refreshed booking limits:", data);

            // Optionally, display the refreshed limits in a popup or UI component
            if (data.status === "success") {
                const dailyLimits = data.data.daily_limits;
                const weeklyLimits = data.data.weekly_limits;

                console.log("[INFO] Updated Daily Limits:", dailyLimits);
                console.log("[INFO] Updated Weekly Limits:", weeklyLimits);
            } else {
                console.error("[ERROR] Failed to refresh booking limits:", data);
            }
        })
        .catch((error) => {
            console.error("[ERROR] Error refreshing booking limits:", error);
        });
}

/**
 * Write booking data to the server.
 */

function writeBookingToServer(slotId, selectedDate, userInfo, row, clickedCell, onSuccess) {
    try {
        const courtId = parseInt(clickedCell.dataset.courtId, 10);
        if (isNaN(courtId)) {
            showDebugPopup({
                status: "error",
                message: "Court ID not found for the selected cell.",
                debug: { clickedCell },
            });
            return;
        }

        const periodCell = row.querySelector(".period-cell");
        const periodId = periodCell ? periodCell.getAttribute("data-period-id") : "Unknown";

        const payload = {
            player_no: userInfo.Mem_No || userInfo.member_no,
            date_container: selectedDate,
            slot_id: slotId,
            selected_court: courtId,
        };

        // Prevent rapid duplicate submissions
        if (isRecentDuplicate(payload)) {
            console.warn("Duplicate booking detected. Skipping POST to server.");
            return;
        }
        storeLastBooking(payload);

        // Show the popup with additional debug information, including period_id
        // showDebugPopup({
        //     status: "success",
        //     message: "Data prepared for database writing.",
        //     data: {
        //         ...payload,
        //         userName: `${userInfo.first_name.charAt(0)} ${userInfo.last_name}`,
        //         period_id: periodId // Add the period_id to the debug info
        //     },
        // });

        // Send POST request to the server
        fetch("/bookings/add", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        })
            .then((response) => response.json())
            .then((data) => {
                console.log("[DEBUG] Booking response:", data);
                if (data.status === "already_booked") {
                    alert("This slot was already taken.");
                    refreshBookingsData(selectedDate);
                    return;
                }
                if (data.error) {
                    console.error("[ERROR] Backend error:", data.error);
                } else {
                    if (data.financial_data) {
                        console.log("[DEBUG] Financial update:", data.financial_data);
                    }
                    updateLightsCredit(data.updated_credit);
                    if (typeof onSuccess === "function") {
                        onSuccess();
                    }
                }
            })
            .catch((error) => {
                console.error("[ERROR] Error saving booking:", error);
                alert("Error saving booking. Please check the console for more details.");
            });
    } catch (error) {
        showDebugPopup({
            status: "error",
            message: "Unexpected error during data preparation for booking.",
            debug: { error },
        });
    }
}



/**
 * Show a popup with debug information.
 * @param {Object} options - Popup content options.
 */
function showDebugPopup({ status, message, data = null, debug = null }) {
    const popup = document.createElement("div");
    popup.style.position = "fixed";
    popup.style.top = "20%";
    popup.style.left = "50%";
    popup.style.transform = "translate(-50%, -20%)";
    popup.style.backgroundColor = "#fff";
    popup.style.border = "1px solid #ccc";
    popup.style.borderRadius = "8px";
    popup.style.padding = "20px";
    popup.style.boxShadow = "0 4px 8px rgba(0, 0, 0, 0.2)";
    popup.style.zIndex = "1000";
    popup.style.width = "400px";
    popup.style.maxHeight = "300px";
    popup.style.overflowY = "auto";

    popup.innerHTML = `
        <h3 style="color: ${status === "success" ? "green" : "red"}">${status.toUpperCase()}</h3>
        <p>${message}</p>
        ${data ? `<pre>${JSON.stringify(data, null, 2)}</pre>` : ""}
        ${debug ? `<pre style="color: gray">${JSON.stringify(debug, null, 2)}</pre>` : ""}
        <button style="margin-top: 10px; padding: 5px 10px;" onclick="document.body.removeChild(this.parentElement)">Close</button>
    `;

    document.body.appendChild(popup);
}

/**
 * Show a popup with booking limit information
 */
function showLimitsPopup({ status, message, limits }) {
    const popup = document.createElement("div");
    popup.style.position = "fixed";
    popup.style.top = "20%";
    popup.style.left = "50%";
    popup.style.transform = "translate(-50%, -20%)";
    popup.style.backgroundColor = "#fff";
    popup.style.border = "1px solid #ccc";
    popup.style.borderRadius = "8px";
    popup.style.padding = "15px";
    popup.style.boxShadow = "0 4px 8px rgba(0, 0, 0, 0.2)";
    popup.style.zIndex = "1000";
    popup.style.width = "auto";
    popup.style.maxWidth = "400px";
    popup.style.maxHeight = "300px";
    popup.style.overflowY = "auto";
    popup.style.fontSize = "12px";

    // Format limits information
    const limitsInfo = limits
        ? `<ul style="list-style-type: disc; padding-left: 20px; margin: 12px 0;">${limits.map(limit => `
            <li style="margin-bottom: 5px; font-size: 12px; line-height: 0.5;">
                <strong>${limit.period_description}:</strong> ${limit.bookings_count} / ${limit.limit}
            </li>
        `).join("")}</ul>`
        : "";

    // Additional message for weekly quota
    const weeklyQuotaMessage = (status === "error" && message.includes("Weekly booking limit"))
        ? `<p style="margin-top: 10px; font-size: 12px; font-style: italic; color: gray;">
            Quota is from Monday to Sunday.
           </p>`
        : "";

    // Set the popup content
    popup.innerHTML = `
        <h3 style="color: ${status === "success" ? "green" : "red"}; font-size: 14px; margin-bottom: 10px;">
            ${message}
        </h3>
        ${limitsInfo}
        ${weeklyQuotaMessage}
        <div style="text-align: center; margin-top: 15px;">
            <button style="padding: 5px 10px;">OK</button>
        </div>
    `;

    // Append the popup to the body
    document.body.appendChild(popup);

    // Add event listener to the OK button
    popup.querySelector("button").addEventListener("click", () => {
        document.body.removeChild(popup);
    });
}







/**
 * Add hover effects to booking cells.
 */
function addHoverEffects() {
    const tableBody = document.getElementById("time_slots_table_body");

    if (!tableBody) {
        console.error("Error: time_slots_table_body element is missing.");
        return;
    }

    const rows = tableBody.querySelectorAll("tr");

    rows.forEach((row) => {
        const courtCells = row.querySelectorAll("td:not(.time-cell)"); // Exclude time cells

        courtCells.forEach((cell) => {
            cell.addEventListener("mouseover", () => {
                cell.classList.add("highlight");
            });

            cell.addEventListener("mouseout", () => {
                cell.classList.remove("highlight");
            });
        });
    });
}

/**
 * Initialize booking-specific functionality.
 * Reattaches the click listener if the table body has been rebuilt.
 */
function initializeBookings() {
    const tableBody = document.getElementById("time_slots_table_body");

    if (!tableBody) {
        console.error("Error: time_slots_table_body element is missing. Booking initialization aborted.");
        return;
    }

    // Rebind the click listener if the table body has changed
    if (boundTableBody !== tableBody) {
        if (boundTableBody) {
            boundTableBody.removeEventListener("click", tableBodyClickListener);
        }
        tableBody.addEventListener("click", tableBodyClickListener);
        boundTableBody = tableBody;
    }

    addHoverEffects();
}

// Reset the bound table body when the courts table is rebuilt
function resetBookingsBinding() {
    if (boundTableBody) {
        boundTableBody.removeEventListener("click", tableBodyClickListener);
        boundTableBody = null;
    }
}

/**
 * Refresh bookings data for the selected date and populate booking cells.
 * Ensures booking data from the database is displayed in the appropriate cells.
 * @param {string} selectedDate - The selected date in dd/MM/yyyy format.
 */
function refreshBookingsData(selectedDate) {
    const formattedDate = reformatDateToDdMmYyyy(selectedDate); // Format the date to dd/MM/yyyy
    console.log("Refreshing bookings for date:", formattedDate);

    fetch(`/main/courts/bookings?date=${formattedDate}`)
        .then((response) => response.json())
        .then((data) => {
            if (!Array.isArray(data)) {
                console.error("Invalid bookings data:", data);
                return;
            }

            // Populate the booking cells with the fetched data
            populateBookingCells(data);
        })
        .catch((error) => {
            console.error("Error refreshing bookings:", error);
        });
}

/**
 * Initialize on document load.
 */
document.addEventListener("DOMContentLoaded", () => {
    const datesContainer = document.getElementById("dates_container");
    const today = new Date();

    // Populate the dates container before linking it to bookings
    populateDatesContainer(datesContainer, today);

    // Link bookings to the dates container
    linkBookingsToDatesContainer();

    // Initialize other functionality
    initializeBookings();
    refreshLegendsData();
});

// Expose initializeBookings globally
window.initializeBookings = initializeBookings;
window.resetBookingsBinding = resetBookingsBinding;
