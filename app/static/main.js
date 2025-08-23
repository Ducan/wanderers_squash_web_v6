// Main JavaScript for mains.js

/**
 * Update the top bar title dynamically and load the correct page.
 * Updated to handle /main/courts and /main/myprofile correctly.
 *
 * @param {string} section - The section name to display in the top bar.
 * @param {Event} [event=null] - Optional event to prevent default navigation.
 */
function updateTopBar(section, event = null) {
    if (event) event.preventDefault(); // Prevent default navigation behavior

    const topBar = document.getElementById("top-bar");
    if (topBar) {
        const sectionName = document.getElementById("section-name");
        if (sectionName) {
            // Update the top-bar heading based on the section
            if (section === "Courts") {
                sectionName.textContent = "Court Booking Schedule";
            } else if (section === "View Bookings") {
                sectionName.textContent = "View this week's bookings"; 
            } else {
                sectionName.textContent = section;
            }
        }
    }
    // Handle specific actions for each link
    switch (section) {
        case "Courts":
            loadContent("/main/courts/"); // Dynamically load courts page
            break;
            case "View Bookings":
                loadContent("/bookings/viewbookings/"); // Dynamically load view bookings page
                break;

        case "My Profile":
            loadContent("/main/myprofile/"); // Dynamically load my profile
            break;
        case "FAQ":
            loadContent("/main/faq/");
            break;
        case "Logout":
            window.location.href = "/logout"; // Redirect to logout
            break;
        default:
            console.warn(`[WARN] No handler for section: ${section}`);
    }
}


// Function to toggle the hamburger menu for the nav-bar
function toggleMenu() {
    const navLinks = document.getElementById('nav-links');
    navLinks.classList.toggle('show'); // Toggle the "show" class to display/hide the menu
}

// Function to collapse the menu when a link is clicked
function collapseMenu() {
    const navLinks = document.getElementById('nav-links');
    navLinks.classList.remove('show'); // Remove the "show" class to hide the menu
}

// Function to fetch and display session information
function displaySessionInfo() {
    fetch('/main/session_info')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.Mem_No) {
                console.log(`Logged in as: ${data.first_name} ${data.last_name} (Mem_No: ${data.Mem_No})`);
            } else {
                console.log('No active session found.');
            }
        })
        .catch(error => {
            console.error('Error fetching session info:', error);
        });
}

// Function to fetch session information and update the session info section
function fetchSessionInfo() {
    fetch('/main/session_info')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            const loggedInAs = document.getElementById('logged-in-as');
            if (data.Mem_No) {
                loggedInAs.textContent = `Logged in as: ${data.first_name} ${data.last_name} (Mem_No: ${data.Mem_No})`;
            } else {
                loggedInAs.textContent = '';
            }
        })
        .catch(error => {
            console.error('Error fetching session info:', error);
            document.getElementById('logged-in-as').textContent = 'Error loading user info.';
        });
}

/**
 * reloadCourtsModule()
 *
 * This function removes any existing <script> element for courts.js,
 * then creates a new one with a cache-busting query parameter.
 * Once the new script loads, it calls initializeCourts().
 *
 * @returns {Promise} - Resolves when courts.js is loaded and initialized.
 */
function reloadCourtsModule() {
    return new Promise((resolve, reject) => {
        // Remove any existing courts.js script element
        const existingScript = document.querySelector('script[src*="courts.js"]');
        if (existingScript) {
            existingScript.parentNode.removeChild(existingScript);
            console.log("[INFO] Removed existing courts.js script element.");
        }

        // Create a new script element with a cache-buster to force a fresh load
        const script = document.createElement("script");
        script.type = "text/javascript";
        script.async = true;
        // Append a query parameter to bypass cache
        script.src = `/static/courts.js?cb=${new Date().getTime()}`;

        script.onload = function() {
            console.log("[INFO] courts.js reloaded successfully.");
            if (typeof window.initializeCourts === "function") {
                window.initializeCourts();
                console.log("[INFO] initializeCourts() executed.");
            } else {
                console.error("[ERROR] initializeCourts() function not found in courts.js");
            }
            resolve();
        };

        script.onerror = function(error) {
            console.error("[ERROR] Failed to load courts.js", error);
            reject(new Error("Failed to load courts.js"));
        };

        // Append the new script to the document body (or head)
        document.body.appendChild(script);
    });
}


/**
 * Load content dynamically into the content container.
 * Ensures that required scripts are loaded, session data is updated, and page-specific initialization is handled.
 *
 * @param {string} url - The URL to fetch content from.
 */
function loadContent(url) {
    console.log(`[INFO] Loading content from: ${url}`);

    fetch(url, { method: "GET", credentials: "same-origin" })
        .then((response) => {
            if (!response.ok) {
                throw new Error(`Error fetching content from ${url}: ${response.statusText}`);
            }
            return response.text();
        })
        .then((htmlContent) => {
            const contentContainer = document.getElementById("content-container");
            if (!contentContainer) {
                console.error("[ERROR] Content container not found. Cannot load content.");
                return;
            }

            // Replace the HTML content
            contentContainer.innerHTML = htmlContent;
            console.log(`[INFO] Content fetched successfully.`);

            // Reload all scripts dynamically
            const scripts = contentContainer.querySelectorAll("script");
            scripts.forEach((script) => {
                const newScript = document.createElement("script");
                if (script.src) {
                    newScript.src = script.src; // Reload external script
                } else {
                    newScript.textContent = script.textContent; // Inline script
                }
                document.body.appendChild(newScript); // Append to body to execute
                document.body.removeChild(newScript); // Cleanup
            });

            console.log("[INFO] Scripts reloaded.");

            // Page-specific handling
            if (url.includes("/main/courts")) {
                console.log("[INFO] Courts page detected. Reinitializing...");
                handleCourtsPage();

            }

            if (url.includes("/bookings/viewbookings")) {
                console.log("[INFO] View Bookings page detected. Reinitializing...");
                handleViewBookingsPage();
            }

            if (url.includes("/main/myprofile")) {
                console.log("[INFO] My Profile page detected. Initializing...");
                handleMyProfilePage();

            }
        })
        .catch((error) => {
            console.error(`[ERROR] Failed to load content from ${url}: ${error.message}`);
        });
}

/**
 * Handles the initialization of the Courts page.
 * Ensures session data is fetched and all required scripts are loaded.
 */
async function handleCourtsPage() {
    console.log("[INFO] Courts page detected. Reinitializing...");

    try {
        // Fetch session info
        const response = await fetch('/main/session_info');
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        const data = await response.json();
        window.user = data; // Update global user object
        console.log("[INFO] Session information loaded:", window.user);

        // Force reload of courts.js and ensure courts are reinitialized
        await loadScript("../static/courts.js");
        console.log("[INFO] courts.js loaded successfully.");

        if (typeof window.initializeCourts === "function") {
            initializeCourts(); // Reinitialize Courts
            console.log("[INFO] Courts initialized successfully.");
        } else {
            throw new Error("initializeCourts function not found.");
        }

        // Reload all other supporting scripts
        await loadWaitingListScript();
        console.log("[INFO] Waiting list script loaded successfully.");
        window.initializePeakPeriodHoverAndClick?.();

        await loadBookingsScript();
        console.log("[INFO] bookings.js loaded successfully.");
        window.initializeBookings?.();

        await loadFinancialsScript();
        console.log("[INFO] Financials script loaded successfully.");

    } catch (error) {
        console.error("[ERROR] Failed to initialize Courts page:", error.message);
    }
}

/**
 * Handles the initialization of the My Profile page.
 * Ensures profile data is fetched and myprofile.js is loaded correctly every time.
 */
async function handleMyProfilePage() {
    console.log("[INFO] My Profile page detected. Initializing...");

    try {
        // Fetch and populate profile data
        const response = await fetch('/main/myprofile/profile_data');
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        const data = await response.json();
        const errorMessageDiv = document.getElementById('errorMessage');

        if (data.error) {
            errorMessageDiv.textContent = data.error;
            errorMessageDiv.style.display = 'block';
            return;
        }

        // Populate profile fields
        document.getElementById('firstName').value = data.first_name || 'N/A';
        document.getElementById('lastName').value = data.surname || 'N/A';
        document.getElementById('memberNo').value = data.member_no || 'N/A';
        document.getElementById('mobile').value = data.cell_phone || 'N/A';
        document.getElementById('email').value = data.email || 'N/A';
        document.getElementById('lightsCredit').value = data.credit || '0.00';

        console.log("[INFO] Profile data populated successfully.");

        // Remove old `myprofile.js` script if exists before reloading it
        document.querySelectorAll('script[src*="myprofile.js"]').forEach(script => script.remove());
        await loadScript("../static/myprofile.js");

        console.log("[INFO] myprofile.js reloaded successfully.");

        // **Fix: Properly bind event listener to Edit Profile button**
        const editButton = document.getElementById("editProfile");
        if (editButton) {
            // Remove any existing event listeners
            const newButton = editButton.cloneNode(true);
            editButton.parentNode.replaceChild(newButton, editButton);

            // Attach click event to toggle editing mode
            newButton.addEventListener("click", function () {
                toggleProfileEditing(newButton);
            });

            console.log("[INFO] Edit Profile button listener attached.");
        }

    } catch (error) {
        console.error("[ERROR] Failed to initialize My Profile page:", error.message);
        const errorMessageDiv = document.getElementById('errorMessage');
        errorMessageDiv.textContent = 'Failed to load profile data. Please try again later.';
        errorMessageDiv.style.display = 'block';
    }
}

function toggleProfileEditing(button) {
    // Select all editable fields except lightsCredit and memberNo
    const fields = document.querySelectorAll('#firstName, #lastName, #mobile, #email');
    const memberNoField = document.getElementById('memberNo'); // Read-only
    const lightsCreditField = document.getElementById('lightsCredit'); // Read-only

    if (button.textContent === 'Edit Profile') {
        // Enable fields for editing
        fields.forEach(field => {
            field.readOnly = false;
            field.style.cursor = 'text';
            field.style.backgroundColor = 'white';
        });

        button.textContent = 'Save Profile'; // Change button text
        console.log("[INFO] Profile fields enabled for editing.");

    } else if (button.textContent === 'Save Profile') {
        // Prepare updated data for submission
        const updatedData = {
            first_name: document.getElementById('firstName').value,
            last_name: document.getElementById('lastName').value,
            member_no: memberNoField.value,
            cell_phone: document.getElementById('mobile').value,
            email: document.getElementById('email').value,
            credit: lightsCreditField.value
        };

        // Send updated data to the backend
        fetch('/main/myprofile/update_profile', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updatedData)
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                alert(`Error: ${data.error}`);
            } else {
                alert('Profile updated successfully.');
            }
        })
        .catch(error => {
            console.error('Error updating profile:', error);
            alert('Failed to update profile. Please try again later.');
        })
        .finally(() => {
            // Lock fields after saving
            fields.forEach(field => {
                field.readOnly = true;
                field.style.cursor = 'not-allowed';
                field.style.backgroundColor = '#f9f9f9';
            });

            button.textContent = 'Edit Profile'; // Change button text back
        });
    }
}

async function handleViewBookingsPage() {
    console.log("[INFO] View Bookings page detected. Ensuring viewbookings.js is loaded...");

    const bookingsScriptUrl = `../static/viewbookings.js`;

    try {
        await loadScript(bookingsScriptUrl);
        console.log("[INFO] viewbookings.js loaded successfully.");

        // Wait until loadBookings is available
        await new Promise((resolve, reject) => {
            let attempts = 0;
            const checkInterval = setInterval(() => {
                if (typeof window.loadBookings === "function") {
                    clearInterval(checkInterval);
                    resolve();
                } else if (attempts >= 10) { // Wait max ~1 sec (10 x 100ms)
                    clearInterval(checkInterval);
                    reject(new Error("Timeout: loadBookings function not available."));
                }
                attempts++;
            }, 100);
        });

        console.log("[INFO] Calling loadBookings...");

        // Fetch session info dynamically
        const response = await fetch('/main/session_info');
        if (!response.ok) {
            throw new Error(`[ERROR] Failed to fetch session info: ${response.status}`);
        }

        const data = await response.json();
        if (!data.Mem_No) {
            console.error("[ERROR] No session info available for the user.");
            return;
        }

        const memNo = data.Mem_No; // Dynamically retrieved
        const currentDate = new Date();
        const startDate = formatDate(currentDate); // Start date is today
        const endDate = formatDate(new Date(currentDate.setDate(currentDate.getDate() + 7))); // End date is 7 days from today

        console.log(`[INFO] Loading bookings for memNo: ${memNo}, startDate: ${startDate}, endDate: ${endDate}`);

        // Call loadBookings
        window.loadBookings(startDate, endDate, memNo);
    } catch (error) {
        console.error("[ERROR] Failed to load viewbookings.js or fetch session info:", error.message);
    }
}


// Helper function to format date as dd/mm/yyyy
function formatDate(date) {
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0'); // Months are 0-indexed
    const year = date.getFullYear();
    return `${day}/${month}/${year}`;
}

/**
 * Dynamically load a script if not already loaded.
 * @param {string} scriptUrl - The URL of the script to load.
 * @returns {Promise} - Resolves when the script is loaded successfully or if it already exists.
 */
function loadScript(scriptUrl) {
    return new Promise((resolve, reject) => {
        // Check if the script is already loaded
        const existingScript = document.querySelector(`script[src="${scriptUrl}"]`);
        if (existingScript) {
            console.log(`[INFO] Script already loaded: ${scriptUrl}`);
            resolve(); // Resolve immediately if the script is already present
            return;
        }

        // Create a new script element
        const script = document.createElement("script");
        script.src = scriptUrl;
        script.type = "text/javascript";
        script.async = true;

        // Event listener for successful script load
        script.onload = () => {
            console.log(`[INFO] Script loaded successfully: ${scriptUrl}`);
            resolve();
        };

        // Event listener for script load errors
        script.onerror = (error) => {
            console.error(`[ERROR] Failed to load script: ${scriptUrl}`);
            reject(new Error(`Failed to load script: ${scriptUrl}`));
        };

        // Append the script to the document body
        document.body.appendChild(script);
    });
}


/**
 * Dynamically load waitinglist.js if not already loaded.
 */
function loadWaitingListScript() {
    return loadScript("../static/waitinglist.js");
}

/**
 * Dynamically load bookings.js if not already loaded.
 */
function loadBookingsScript() {
    return loadScript("../static/bookings.js");
}

/**
 * Dynamically load financials.js if not already loaded.
 */
function loadFinancialsScript() {
    return loadScript("../static/financials.js");
}

/**
 * Attach event listeners to nav-bar links dynamically and handle session info.
 */
document.addEventListener("DOMContentLoaded", () => {
    // Populate the "Logged in as" info
    fetchSessionInfo();

    // Set "Courts" as the default page
    updateTopBar("Courts");

    // Check if the user is on the Courts page on page load and reinitialize
    if (window.location.pathname.includes("/main/courts")) {
        console.log("[INFO] Courts page detected on page load. Initializing...");
        handleCourtsPage();
    }

    // Select all navigation links
    const navLinks = document.querySelectorAll(".nav-links a");

    // Add click event listeners to each navigation link
    navLinks.forEach((link) => {
        link.addEventListener("click", (event) => {
            const href = link.getAttribute("href");
            const isExternal = href && (href.startsWith("http://") || href.startsWith("https://"));
    
            // Skip handling for external links
            if (isExternal) {
                console.log(`[INFO] External link clicked: ${href}`);
                return;
            }
    
            const section = event.target.textContent.trim();
    
            // Update the top bar with the selected section
            updateTopBar(section, event);
    
            // Collapse the menu after a link is clicked
            collapseMenu();
        });
    });
});


/**
 * Ensures the browser history starts fresh at `/main/` after login
 * and prevents the back button from navigating to the login page.
 */
window.addEventListener("load", function () {
    console.log("[INFO] Clearing history and forcing /main/ as the only entry.");

    // Remove login page from history and force `/main/` as the first entry
    history.pushState(null, "", "/main/");
    history.replaceState(null, "", "/main/");
});

/**
 * Overrides the back button behavior to always reload `/main/`.
 * Prevents duplicate navigation bars and ensures proper page initialization.
 */

window.addEventListener("popstate", function () {
    console.log("[INFO] Back button pressed. Reloading default page (Courts) to prevent duplicate nav-bar.");

    // ✅ Instead of just using loadContent(), force a full page reload to avoid duplicate elements
    window.location.href = "/main/";

    // ✅ Ensure the history is still set correctly to prevent further back navigation
    setTimeout(() => {
        history.replaceState(null, "", "/main/");
    }, 0);
});

