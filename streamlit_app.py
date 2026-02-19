import streamlit as st

# File upload section
title = "Baja Tenis"

st.title(title)

uploaded_file = st.file_uploader("Choose a file")

if uploaded_file is not None:
    try:
        # Read the file and process it
        data = uploaded_file.read()  # Adjust according to the file type

        # Process your data here
        st.success("File processed successfully!")
    except Exception as e:
        st.error(f"Error occurred while processing the file: {e}")
else:
    st.warning("Please upload a file to proceed.")

# Additional streamlit components
