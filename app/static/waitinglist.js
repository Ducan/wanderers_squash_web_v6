/**
 * JavaScript for handling the waiting list functionality.
 * Includes adding a user to the waiting list, displaying waiting list status,
 * and hover effects for time column cells aligned with peak periods.
 */

/**
 * Reformat date from yyyy-MM-dd to dd/MM/yyyy.
 * @param {string} date - The date in yyyy-MM-dd format.
 * @returns {string} - The date in dd/MM/yyyy format.
 */
function formatDateToDDMMYYYY(date) {
    const [year, month, day] = date.split("-");
    return `${day}/${month}/${year}`;
}

document.addEventListener("DOMContentLoaded", () => {
    initializePeakPeriodHoverAndClick();
});

/**
 * Add hover and click functionality to time column cells aligned with peak periods.
 */
function initializePeakPeriodHoverAndClick() {
    const timeCells = document.querySelectorAll(".time-cell");

    timeCells.forEach((timeCell) => {
        const row = timeCell.closest("tr"); // Find the row corresponding to the time cell
        const periodCell = row.querySelector(".period-cell"); // Find the period cell in the same row
        const periodAbbreviation = periodCell?.textContent.trim().toUpperCase();

        // Only apply to peak period cells ("P")
        if (periodAbbreviation === "P") {
            const dateBlock = document.querySelector(".date-block.selected"); // Get the selected date block
            const originalColor = window.getComputedStyle(dateBlock).backgroundColor; // Color from dates_container

            // Add the waiting-list-cell class to identify waiting list cells
            timeCell.classList.add("waiting-list-cell");

            // Set initial text color for waiting list cells
            timeCell.style.color = "#FFF";

            // Add hover effect
            timeCell.addEventListener("mouseover", () => {
                timeCell.style.backgroundColor = "#555"; // Set hover color to #555
            });

            timeCell.addEventListener("mouseout", () => {
                timeCell.style.backgroundColor = originalColor; // Revert to the color from dates_container
            });

            // Add click event to add to the waiting list
            timeCell.addEventListener("click", () => {
                const selectedDate = getSelectedDate(); // Utility from courts.js
                const selectedTime = timeCell.textContent; // Time text from the time cell

                if (!selectedDate) {
                    alert("Please select a date first.");
                    return;
                }

                // Add the user to the waiting list
                addToWaitingList(selectedDate, selectedTime);
            });
        }
    });
}


/**
 * Send a POST request to add the current user to the waiting list for a specific time slot.
 * Displays a popup on success or failure.
 * @param {string} date - The selected date (dd/MM/yyyy format).
 * @param {string} timeSlot - The selected time slot (HH:MM format).
 */
function addToWaitingList(date, timeSlot) {
    fetch(`${window.location.origin}/waitinglist/add`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ date, time_slot: timeSlot }),
    })
        .then((response) => response.json())
        .then((data) => {
            if (data.already_in_list) {
                // Show popup with removal option
                showWaitingListPopup(
                    "warning",
                    "Player Already in Waiting List",
                    "You are already on this waiting list. Do you want to remove yourself?",
                    null,
                    () => {
                        // On confirmation, trigger removal
                        removeFromWaitingList(date, timeSlot);
                    }
                );
            } else {
                // Show success popup for addition
                showWaitingListPopup("success", "Success", data.message, data.email_address);
            }
        })
        .catch((error) => {
            console.error("Error adding to waiting list:", error.message);
            showWaitingListPopup("error", "Error", error.message);
        });
}




function removeFromWaitingList(date, timeSlot) {
    const formattedDate = formatDateToDDMMYYYY(date);

    console.log("Removing:", { date: formattedDate, timeSlot });

    fetch(`${window.location.origin}/waitinglist/remove`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ date: formattedDate, time_slot: timeSlot }),
    })
        .then((response) => {
            if (!response.ok) {
                return response.json().then((data) => {
                    throw new Error(data.error || "An unknown error occurred.");
                });
            }
            return response.json();
        })
        .then((data) => {
            console.log("Removed successfully:", data);
            showWaitingListPopup("success", "Success", data.message);
        })
        .catch((error) => {
            console.error("Error removing from waiting list:", error.message);
            showWaitingListPopup("error", "Error", error.message);
        });
}


/**
 * Display a popup with waiting list confirmation or error information.
 * @param {string} type - The type of the message ('success' or 'error').
 * @param {string} title - The title of the popup.
 * @param {string} message - The message content.
 * @param {string} [emailAddress] - The email address associated with the confirmation (optional).
 */
function showWaitingListPopup(type, title, message, emailAddress = null, onConfirm = null) {
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

    // Add email address and note if provided
    const emailInfo = emailAddress
        ? `<p style="font-size: 12px; margin-top: 10px;">
            Notification will be sent to: <strong>${emailAddress}</strong><br>
            Please update your email address in My Profile if required.
        </p>`
        : "";

    const confirmButton = onConfirm
        ? `<button style="padding: 3px 8px; margin-right: 10px;">Yes</button>
           <button style="padding: 3px 8px;">No</button>`
        : `<button style="padding: 3px 8px;">OK</button>`;

    popup.innerHTML = `
        <h3 style="color: ${
            type === "success"
                ? "green"
                : type === "error"
                ? "red"
                : "orange"
        }; font-size: 14px; margin-bottom: 10px;">
            ${title}
        </h3>
        <p>${message}</p>
        ${emailInfo}
        <div style="text-align: center; margin-top: 15px;">
            ${confirmButton}
        </div>
    `;

    document.body.appendChild(popup);

    const buttons = popup.querySelectorAll("button");
    if (onConfirm) {
        buttons[0].addEventListener("click", () => {
            onConfirm();
            document.body.removeChild(popup);
        });
        buttons[1].addEventListener("click", () => {
            document.body.removeChild(popup);
        });
    } else {
        buttons[0].addEventListener("click", () => {
            document.body.removeChild(popup);
        });
    }
}

// Expose initializePeakPeriodHoverAndClick globally
window.initializePeakPeriodHoverAndClick = initializePeakPeriodHoverAndClick;

