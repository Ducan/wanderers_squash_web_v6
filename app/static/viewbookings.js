/**
 * Fetch and display bookings for the logged-in user based on `mem_no`.
 * Filters bookings and dynamically populates the table.
 * @param {string} startDate - Start date in "dd/mm/yyyy" format.
 * @param {string} endDate - End date in "dd/mm/yyyy" format.
 * @param {number} memNo - The logged-in user's `mem_no`.
 */
function loadBookings(startDate, endDate, memNo) {
    console.log(`[DEBUG] Fetching bookings for: ${startDate} to ${endDate} for memNo: ${memNo}`); // Debug log

    const url = `/bookings/viewbookings?start_date=${encodeURIComponent(startDate)}&end_date=${encodeURIComponent(endDate)}`;

    fetch(url)
        .then((response) => {
            if (!response.ok) {
                throw new Error(`Error fetching bookings: ${response.status} ${response.statusText}`);
            }
            return response.json();
        })
        .then((data) => {
            if (data.error) {
                console.error("[ERROR] Backend error:", data.error);
                alert(`Error: ${data.error}`);
                return;
            }

            const bookingsTable = document.getElementById("bookings-table");
            if (!bookingsTable) {
                console.error("[ERROR] Bookings table not found in the DOM.");
                return;
            }

            bookingsTable.innerHTML = ""; // Clear the table

            // Populate bookings dynamically
            if (data.bookings.length === 0) {
                bookingsTable.innerHTML = "<tr><td colspan='4'>No bookings found for the selected range.</td></tr>";
                return;
            }

            data.bookings.forEach((booking) => {
                const bookingDateTime = new Date(`${booking.date.split("/").reverse().join("-")}T${booking.time}`);
                const currentDateTime = new Date();

                // Ensure `date_container` and `slot_id` are available
                const dateContainer = booking.date_container || booking.date.split("/").reverse().join("-");
                const slotId = booking.slot_id;

                // Check if booking is in the past
                const isPastBooking = bookingDateTime < currentDateTime;

                const cancelButton = isPastBooking
                    ? `<button class="cancel-btn" disabled style="cursor: not-allowed; opacity: 0.5;">Cannot Cancel</button>`
                    : `<button class="cancel-btn" onclick="cancelBooking('${dateContainer}', '${slotId}', '${booking.player_no_column}', '${booking.player_no}', '${booking.selected_court}')">Cancel</button>`;

                const row = `
                    <tr>
                        <td>${booking.date}</td>
                        <td>${booking.time}</td>
                        <td>${booking.court_description || "Unknown"}</td>
                        <td>${cancelButton}</td>
                    </tr>
                `;
                bookingsTable.innerHTML += row;
            });
        })
        .catch((error) => {
            console.error("[ERROR] Error loading bookings:", error);
            alert("Failed to load bookings. Please try again later.");
        });
}

/**
 * Cancel a booking for the logged-in user.
 * @param {string} date_container - Booking date in ISO format (YYYY-MM-DD).
 * @param {string|number} slot_id - Identifier for the selected time slot.
 * @param {string} playerNoColumn - The column representing the player number for the court.
 * @param {number|string} memNo - The logged-in user's `mem_no`.
 * @param {number} selectedCourt - The court number.
 */
function cancelBooking(date_container, slot_id, playerNoColumn, memNo, selectedCourt) {
    // Prepare the payload
    const payload = {
        date_container,
        slot_id,
        player_no_column: playerNoColumn, // e.g., "PlayerNo_2"
        player_no: Number(memNo),
        selected_court: selectedCourt,
    };

    console.log("[DEBUG] Payload for cancellation:", payload); // Debug log

    // Send the payload to the delete endpoint
    fetch("/bookings/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    })
        .then((response) => response.json())
        .then((data) => {
            if (data.error) {
                console.error("[ERROR] Backend error:", data.error);
                alert(`Error: ${data.error}`);
                return;
            }

            alert("Booking canceled successfully.");
            // Reload bookings after deletion
            const currentDate = new Date();
            const startDate = formatDate(currentDate); // Start date is today

            const endDateObj = new Date();
            endDateObj.setDate(currentDate.getDate() + 7);
            const endDate = formatDate(endDateObj); // End date (7 days later)

            loadBookings(startDate, endDate, memNo);
        })
        .catch((error) => {
            console.error("[ERROR] Error canceling booking:", error);
            alert("Failed to cancel booking. Please try again later.");
        });
}

/**
 * Utility to format date as "dd/mm/yyyy".
 * @param {Date} date - The date object.
 * @returns {string} - The date in "dd/mm/yyyy" format.
 */
function formatDate(date) {
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0'); // Months are 0-indexed
    const year = date.getFullYear();
    return `${day}/${month}/${year}`;
}

/**
 * Initialize the view bookings functionality on document load.
 */
document.addEventListener("DOMContentLoaded", () => {
    console.log("[INFO] Initializing View Bookings...");

    // Fetch user session info dynamically
    fetch('/main/session_info')
        .then(response => response.json())
        .then(data => {
            if (!data.Mem_No) {
                console.error("[ERROR] No session info available for the user.");
                return;
            }

            const memNo = data.Mem_No; // Dynamically retrieved
            const currentDate = new Date();
            const startDate = formatDate(currentDate); // Start date is today

            const endDateObj = new Date();
            endDateObj.setDate(currentDate.getDate() + 7);
            const endDate = formatDate(endDateObj); // End date (7 days later)

            console.log(`[DEBUG] View Bookings URL: /bookings/viewbookings?start_date=${startDate}&end_date=${endDate}`); // Debugging output

            loadBookings(startDate, endDate, memNo);
        })
        .catch(error => {
            console.error("[ERROR] Failed to fetch session info:", error.message);
        });
});
