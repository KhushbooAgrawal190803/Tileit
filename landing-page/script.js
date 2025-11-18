// Open Buy Now Form Modal
function openBuyNowForm() {
    const modal = document.getElementById('buyNowModal');
    modal.style.display = 'block';
    document.body.style.overflow = 'hidden'; // Prevent background scrolling
}

// Close Buy Now Form Modal
function closeBuyNowForm() {
    const modal = document.getElementById('buyNowModal');
    modal.style.display = 'none';
    document.body.style.overflow = 'auto'; // Restore scrolling
}

// Handle Buy Now Form Submission
function handleBuyNow(event) {
    event.preventDefault();
    
    // Get form values
    const email = document.getElementById('email').value;
    const zipcode = document.getElementById('zipcode').value;
    const marketing = document.getElementById('marketing').checked;
    
    // Validate email
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
        alert('Please enter a valid email address');
        return;
    }
    
    // Validate zipcode
    const zipRegex = /^\d{5}$/;
    if (!zipRegex.test(zipcode)) {
        alert('Please enter a valid 5-digit ZIP code');
        return;
    }
    
    // Close the form modal
    closeBuyNowForm();
    
    // Show area not available popup
    setTimeout(() => {
        showAreaPopup();
    }, 300);
    
    // Here you could also send the data to a backend API
    console.log('Form submitted:', {
        email: email,
        zipcode: zipcode,
        marketing: marketing
    });
}

// Show Area Not Available Popup
function showAreaPopup() {
    const popup = document.getElementById('areaPopup');
    popup.style.display = 'flex';
    document.body.style.overflow = 'hidden'; // Prevent background scrolling
}

// Close Area Not Available Popup
function closeAreaPopup() {
    const popup = document.getElementById('areaPopup');
    popup.style.display = 'none';
    document.body.style.overflow = 'auto'; // Restore scrolling
    
    // Reset form
    document.getElementById('buyNowForm').reset();
}

// Close modals when clicking outside
window.onclick = function(event) {
    const buyNowModal = document.getElementById('buyNowModal');
    const areaPopup = document.getElementById('areaPopup');
    
    if (event.target === buyNowModal) {
        closeBuyNowForm();
    }
    
    if (event.target === areaPopup) {
        closeAreaPopup();
    }
}

// Close modals with Escape key
document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        closeBuyNowForm();
        closeAreaPopup();
    }
});

