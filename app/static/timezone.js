// Detect the user's time zone using the browser's Intl API
const userTimeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;

// Send the detected time zone to the Flask server
fetch('/set-timezone', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
    },
    body: JSON.stringify({ timezone: userTimeZone }),
})
    .then(response => response.json())
    .then(data => {
        console.log('Time zone set response:', data);
    })
    .catch(error => {
        console.error('Error setting time zone:', error);
    });
