import streamlit as st
import requests
from datetime import time as dt_time
import re

API_URL = "https://your-fastapi-app.up.railway.app"


# Page Configuration
st.set_page_config(page_title="Doctor Appointment App", page_icon="🏥")

# ------------------ Background Styling ------------------
def set_bg():
    st.markdown(
        """
        <style>
        .stApp {
            background-image: url("https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=1350&q=80");
            background-size: cover;
            background-position: center;
            background-repeat: no-repeat;
            background-attachment: fixed;
            color: white;
        }
        .stApp::before {
            content: "";
            position: fixed;
            top: 0; left: 0;
            width: 100vw; height: 100vh;
            background-color: rgba(0,0,0,0.5);
            z-index: -1;
        }
        h1, h2, h3, h4, h5, h6, .stTextInput label, .stSelectbox label, .stNumberInput label {
            color: white !important;
            font-weight: bold !important;
        }
    
        h1, h2, h3, h4, h5, h6, .stTextInput label, .stSelectbox label, .stNumberInput label {
        color: white !important;
        font-weight: bold !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

set_bg()

# ------------------ Gmail Validation ------------------
def is_valid_gmail(email):
    return re.match(r"^[a-zA-Z0-9_.+-]+@gmail\.com$", email)

# ------------------ Header and Logo ------------------
st.write("🩺 Book your doctor visits easily with this app.")
if st.button("📅 Book Appointment"):
    st.success("Appointment booked!")
st.image("https://cdn-icons-png.flaticon.com/512/3771/3771585.png", width=80)

# ------------------ Session State ------------------
if "token" not in st.session_state:
    st.session_state.token = None
if "role" not in st.session_state:
    st.session_state.role = None
if "user_id" not in st.session_state:
    st.session_state.user_id = None

# ------------------ Sidebar Menu ------------------
if st.session_state.role == "patient":
    menu = ["Home", "Signup", "Login", "Doctors", "My Appointments"]
elif st.session_state.role == "doctor":
    menu = ["Home", "Signup", "Login", "My Appointments"]
else:
    menu = ["Home", "Signup", "Login"]

choice = st.sidebar.selectbox("Menu", menu)

if st.session_state.token:
    if st.sidebar.button("Logout"):
        st.session_state.token = None
        st.session_state.role = None
        st.session_state.user_id = None
        st.success("Logged out successfully.")

# ------------------ Home Page ------------------
if choice == "Home":
    st.title("🏥 Doctor Appointment Booking")
    st.write("Book your doctor visits easily with this app.")

# ------------------ Signup Page ------------------
elif choice == "Signup":
    st.markdown("<h2>Create Account</h2>", unsafe_allow_html=True)
    name = st.text_input("Name")
    email = st.text_input("Email (must be Gmail)")
    password = st.text_input("Password", type="password")
    role = st.selectbox("Role", ["patient", "doctor"])
    specialty = st.text_input("Specialty (if doctor)")
    fees = st.number_input("Fees (if doctor)", min_value=0)

    if st.button("Signup"):
        if not is_valid_gmail(email):
            st.error("Please enter a valid Gmail address like example@gmail.com.")
        elif not name or not password:
            st.error("Name and password are required.")
        else:
            specialty_val = specialty.strip() if role == "doctor" else None
            fees_val = int(fees) if role == "doctor" else None

            payload = {
                "name": name,
                "email": email,
                "password": password,
                "role": role,
                "specialty": specialty_val,
                "fees": fees_val
            }

            try:
                r = requests.post(f"{API_URL}/signup", json=payload)
                if r.status_code == 200:
                    st.success(r.json().get("message", "Signup successful!"))
                else:
                    st.error(r.json().get("detail", "Signup failed"))
            except Exception as e:
                st.error(f"Error: {e}")

# ------------------ Login Page ------------------
elif choice == "Login":
    st.subheader("Login")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        try:
            r = requests.post(f"{API_URL}/login", json={"email": email, "password": password})
            if r.status_code == 200:
                data = r.json()
                st.session_state.token = data.get("access_token")
                st.session_state.role = data.get("role")
                st.session_state.user_id = data.get("id")
                st.success("Logged in successfully!")
            else:
                st.error(r.json().get("detail", "Invalid credentials"))
        except Exception as e:
            st.error(f"Error: {e}")

# ------------------ Doctors Page ------------------
elif choice == "Doctors":
    if not st.session_state.token:
        st.error("Please login to view and book doctors.")
    else:
        st.subheader("Available Doctors")
        try:
            r = requests.get(f"{API_URL}/doctors")
            if r.status_code == 200:
                for doc in r.json():
                    st.markdown(f"### {doc['name']}")
                    st.write(f"**Specialty:** {doc.get('specialty', 'N/A')}")
                    st.write(f"**Fees:** ₹{doc.get('fees', 'N/A')}")
                    date = st.date_input(f"Select date for {doc['name']}", key=f"date_{doc['id']}")
                    appointment_time = st.time_input(f"Select time for {doc['name']}", key=f"time_{doc['id']}", value=dt_time(9, 0))

                    if st.button(f"Book with {doc['name']}", key=f"book_{doc['id']}"):
                        payload = {
                            "doctor_id": doc["id"],
                            "date": str(date),
                            "time": appointment_time.strftime("%H:%M")
                        }
                        headers = {"Authorization": f"Bearer {st.session_state.token}"}
                        res = requests.post(f"{API_URL}/appointments", json=payload, headers=headers)
                        if res.status_code == 200:
                            st.success(res.json().get("message", "Appointment booked!"))
                        else:
                            st.error(res.json().get("detail", "Booking failed"))
                    st.markdown("---")
            else:
                st.error("Failed to fetch doctors list.")
        except Exception as e:
            st.error(f"Error: {e}")

# ------------------ My Appointments Page ------------------
elif choice == "My Appointments":
    if not st.session_state.token:
        st.error("Please login first.")
    else:
        st.subheader("My Appointments")
        try:
            r = requests.get("http://example.com/api")
            headers = {"Authorization": f"Bearer {st.session_state.token}"}
            r = requests.get(f"{API_URL}/appointments", headers=headers)
            if r.status_code == 200:
                appointments = r.json()
                if appointments:
                    for appt in appointments:
                        if st.session_state.role == "doctor":
                            st.write(f"Appointment with Patient: {appt['patient_name']} | Date: {appt['date']} | Time: {appt.get('time', 'Not set')} | Status: {appt['status']}")
                            
                            if appt['status'] == "pending":
                                new_status = st.selectbox(
                                    f"Change status for appointment {appt['id']}",
                                    ["pending", "accepted", "rejected"],
                                    index=0,
                                    key=f"status_{appt['id']}"
                                )
                                new_time = st.time_input(
                                    f"Set time for appointment {appt['id']}",
                                    key=f"time_{appt['id']}",
                                    value=dt_time(9, 0)
                                )

                                if st.button(f"Update Appointment {appt['id']}", key=f"update_{appt['id']}"):
                                    payload = {
                                        "status": new_status,
                                        "time": new_time.strftime("%H:%M")
                                    }
                                    res = requests.put(
                                        f"{API_URL}/appointments/{appt['id']}",
                                        json=payload,
                                        headers=headers
                                    )
                                    if res.status_code == 200:
                                        st.success("Appointment updated successfully!")
                                    else:
                                        st.error(f"Failed to update: {res.json().get('detail', 'Error')}")
                        
                        elif st.session_state.role == "patient":
                            st.write(f"Appointment with Doctor: {appt['doctor_name']} | Date: {appt['date']} | Time: {appt.get('time', 'Not set')} | Status: {appt['status']}")
                        
                        st.markdown("---")
        except Exception as e:
            st.error(f"Error: {e}")

