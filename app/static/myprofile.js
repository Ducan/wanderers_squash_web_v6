/*
========================================
   Profile Management Script
   Description: This script manages profile data fetching, displaying, editing, and updating.
   Key Features:
   - Fetch and display profile data from the backend.
   - Allow editing of certain fields, while keeping `Lights Credit` and `Member No` read-only.
   - Update profile data to the backend on save.
========================================
*/

(function () {
    // Fetch profile data from the backend
    fetch('/main/myprofile/profile_data')
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            // Display error message if the backend returns an error
            const errorMessageDiv = document.getElementById('errorMessage');
            if (data.error) {
                errorMessageDiv.textContent = data.error;
                errorMessageDiv.style.display = 'block';
                return;
            }

            // Populate profile fields with the fetched data
            document.getElementById('firstName').value = data.first_name || 'N/A';
            document.getElementById('lastName').value = data.surname || 'N/A';
            document.getElementById('memberNo').value = data.member_no || 'N/A';
            document.getElementById('mobile').value = data.cell_phone || 'N/A';
            document.getElementById('email').value = data.email || 'N/A';
            document.getElementById('lightsCredit').value = data.credit || '0.00';
        })
        .catch(error => {
            // Log errors and show a user-friendly message on failure
            console.error('Error fetching profile data:', error);
            const errorMessageDiv = document.getElementById('errorMessage');
            errorMessageDiv.textContent = 'Failed to load profile data. Please try again later.';
            errorMessageDiv.style.display = 'block';
        });

    // Add logic to toggle between editing and saving when the Edit button is clicked
    const editButton = document.getElementById('editProfile');
    editButton.addEventListener('click', function () {
        // Select all editable fields except lightsCredit and memberNo
        const fields = document.querySelectorAll('#firstName, #lastName, #mobile, #email');
        const memberNoField = document.getElementById('memberNo'); // Keep memberNo read-only
        const lightsCreditField = document.getElementById('lightsCredit'); // Keep lightsCredit read-only

        if (editButton.textContent === 'Edit Profile') {
            // Enable fields for editing (excluding lightsCredit and memberNo)
            fields.forEach(field => {
                field.readOnly = false;
                field.style.cursor = 'text';
                field.style.backgroundColor = 'white';
            });
            editButton.textContent = 'Save Profile';
        } else {
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
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(updatedData)
            })
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        alert(`Error: ${data.error}`);
                    } else {
                        alert('Profile updated successfully.');
                        fetchSessionInfo();
                    }
                })
                .catch(error => {
                    console.error('Error updating profile:', error);
                    alert('Failed to update profile. Please try again later.');
                })
                .finally(() => {
                    fields.forEach(field => {
                        field.readOnly = true;
                        field.style.cursor = 'not-allowed';
                        field.style.backgroundColor = '#f9f9f9';
                    });
                    editButton.textContent = 'Edit Profile';
                });
        }
    });
})();

