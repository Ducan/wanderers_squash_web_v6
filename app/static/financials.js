/**
 * Calculate credit for a booking or cancellation.
 *
 * @param {number} memNo - The member number.
 * @param {string} costType - The cost type ('IBOOKING' or 'ICANCEL').
 * @param {function} callback - A callback function to handle the response.
 */
function deductCredit(memNo, costType, callback) {
    const payload = {
        mem_no: memNo,
        cost_type: costType
    };

    fetch('/financials/calculated_internet_bookings', { // Updated endpoint
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
        .then(response => {
            if (!response.ok) {
                throw new Error(`Error: ${response.status} ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.error) {
                callback({ success: false, message: data.error, request_payload: payload });
                return;
            }

            // Pass successful response to callback
            callback({
                success: true,
                cost: data.cost,
                updated_credit: data.updated_credit,
                request_payload: payload
            });
        })
        .catch(error => {
            callback({ success: false, message: error.message, request_payload: payload });
        });
}

// No specific initialization needed, but ensure deductCredit is accessible if required
window.deductCredit = deductCredit;
