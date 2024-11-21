import streamlit as st
import time
import pandas as pd
import os
from io import BytesIO
# Set the theme to light mode

# Your app code continues here

# Define a base directory for saving outputs
OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)  # Ensure the output directory exists

# Function to handle file download in Streamlit
def download_file(file_path):
    with open(file_path, "rb") as f:
        file_data = f.read()
    return BytesIO(file_data)

# Function to assign rooms (same logic as in the Flask version)
def assign_rooms(courses, students_df, rooms_df, buffer, sparse):
    assignments = []
    room_capacity_left = rooms_df[['Room No.', 'Exam Capacity']].copy()
    room_capacity_left['Remaining Capacity'] = room_capacity_left['Exam Capacity'] - buffer

    for course in courses:
        students = students_df[students_df['course_code'] == course][['rollno', 'Name']].values.tolist()
        num_students = len(students)

        for _, room in room_capacity_left.iterrows():
            if room['Remaining Capacity'] <= 0:
                continue

            max_students_in_room = min(room['Remaining Capacity'], num_students)
            if sparse:
                max_students_in_room = min(max_students_in_room, room['Exam Capacity'] // 2)

            assigned_students = max_students_in_room
            assigned_roll_numbers_and_names = students[:assigned_students]
            students = students[assigned_students:]
            num_students -= assigned_students

            room_capacity_left.loc[room_capacity_left['Room No.'] == room['Room No.'], 'Remaining Capacity'] -= assigned_students

            assignments.append({
                'Room': room['Room No.'],
                'Block': rooms_df.loc[rooms_df['Room No.'] == room['Room No.'], 'Block'].values[0],
                'Course': course,
                'Students Assigned': assigned_students,
                'Vacant Seats': room_capacity_left.loc[room_capacity_left['Room No.'] == room['Room No.'], 'Remaining Capacity'].values[0],
                'Roll Numbers and Names': assigned_roll_numbers_and_names,
                'Buffer Seats': buffer
            })

            if num_students == 0:
                break

        if num_students > 0:
            st.warning(f"Warning: Not enough rooms for course {course} with {num_students} students remaining.")

    return assignments

# Streamlit app
def app():
    # Adding animation to the title
    st.markdown("""
        <style>
            .animated-title {
                animation: slideIn 3s ease-in-out forwards;
                opacity: 0;
            }

            @keyframes slideIn {
                0% { transform: translateX(-100%); opacity: 0; }
                100% { transform: translateX(0); opacity: 1; }
            }
        </style>
        <h1 class="animated-title">📚 Seating Arrangement Tool</h1>
    """, unsafe_allow_html=True)
    
  

    st.markdown(
        """
        This tool helps you create seating arrangements for exam halls based on student, room, and schedule data.
        Upload the necessary files and configure your seating preferences.
        """
    )
    st.markdown(
    """
    <style>
    /* Resize file uploaders */
    .stFileUploader {
        max-width: 300px;
        margin: 0 auto;
    }
    .stFileUploader > div > div {
        height: 40px;
    }

    /* Resize download buttons */
    .stDownloadButton {
        max-width: 200px;
        padding: 5px 10px;
        font-size: 12px;
        margin-bottom: 10px;
    }
    </style>
    """,
    unsafe_allow_html=True
)


    # Upload files section
    with st.expander("📁 Upload Files", expanded=True):

         # Create a grid with columns
        col1, col2 = st.columns(2)  # Two columns in the grid layout
        with col1:
         students_file = st.file_uploader("Upload Students File", type=["csv"], help="Upload a CSV file with student data.", key="students")
         schedule_file = st.file_uploader("Upload Schedule File", type=["csv"], help="Upload a CSV file with class schedule.", key="schedule")
        with col2:
         rooms_file = st.file_uploader("Upload Rooms File", type=["csv"], help="Upload a CSV file with room details.", key="rooms")
         student_names_file = st.file_uploader("Upload Student Names File", type=["csv"], help="Upload a CSV file with student names.", key="names")

    # User inputs for buffer and seating
    with st.expander("📝 Configuration Options", expanded=True):
        buffer = st.number_input("Enter buffer seats:", min_value=0, step=1, value=0)
        sparse_option = st.radio("Seating Option", ('Dense', 'Sparse'))
        sparse = sparse_option == 'Sparse'

    if st.button("Generate Seating Arrangement"):
        if students_file and schedule_file and rooms_file and student_names_file:
            # Show loader animation
            placeholder = st.empty()  # Create a placeholder for the loader
            for frame in ["🚀", "📖", "⏳", "🛠️", "✨"]:
                placeholder.markdown(f"<h2 style='text-align: center;'>{frame} Generating seating arrangement... Please wait</h2>", unsafe_allow_html=True)
                time.sleep(0.75)  # Simulate loading time

            # Clear loader after processing
            placeholder.empty()
            # Load data
            students_df = pd.read_csv(students_file, skiprows=1)
            schedule_df = pd.read_csv(schedule_file, skiprows=1)
            rooms_df = pd.read_csv(rooms_file)
            student_names_df = pd.read_csv(student_names_file)

            # Merge student names with roll numbers
            students_df = pd.merge(students_df, student_names_df[['Roll', 'Name']], left_on='rollno', right_on='Roll', how='left')

            # Parse courses
            schedule_df['Morning Courses'] = schedule_df['Morning'].apply(lambda x: x.split('; ') if pd.notna(x) else [])
            schedule_df['Evening Courses'] = schedule_df['Evening'].apply(lambda x: x.split('; ') if pd.notna(x) else [])

            file_paths = []
            all_data = []
            combined_data = []

            # Process each row in the schedule
            for _, row in schedule_df.iterrows():
                date = row['Date']
                day = row['Day']

                for session, courses in [('Morning', row['Morning Courses']), ('Evening', row['Evening Courses'])]:
                    assignments = assign_rooms(courses, students_df, rooms_df, buffer, sparse)

                    for assignment in assignments:
                        course = assignment['Course']
                        room = assignment['Room']

                        # Prepare a folder structure for the date
                        date_folder = os.path.join(OUTPUT_DIR, date.replace('/', '-'))
                        os.makedirs(date_folder, exist_ok=True)

                        # Prepare file name
                        file_name = f"{date.replace('/', '-')}_{session}_{course}_{room}.xlsx"
                        file_path = os.path.join(date_folder, file_name)

                        # Format roll numbers and names for saving
                        roll_numbers_and_names_df = pd.DataFrame(assignment['Roll Numbers and Names'], columns=['Roll No.', 'Name'])
                        roll_numbers_and_names_df['Signature'] = ""  # Add empty Signature column

                        # Add signature space at the bottom
                        signature_space = pd.DataFrame({'Roll No.': [''], 'Name': ['Invigilator Signature:'], 'Signature': ['']})
                        signature_space = pd.concat([signature_space, pd.DataFrame({'Roll No.': [''], 'Name': ['TA Signature:'], 'Signature': ['']})])

                        # Combine data and signature space
                        final_df = pd.concat([roll_numbers_and_names_df, signature_space], ignore_index=True)

                        # Include additional metadata
                        metadata = {
                            'Date': date,
                            'Day': day,
                            'Session': session,
                            'Course': course,
                            'Room': room,
                            'Block': assignment['Block'],
                            'Students Assigned': assignment['Students Assigned'],
                            'Vacant Seats': assignment['Vacant Seats'],
                            'Buffer Seats': assignment['Buffer Seats']
                        }
                        metadata_df = pd.DataFrame(metadata.items(), columns=['Key', 'Value'])

                        # Write to individual Excel file
                        with pd.ExcelWriter(file_path) as writer:
                            metadata_df.to_excel(writer, index=False, sheet_name='Metadata')
                            final_df.to_excel(writer, index=False, sheet_name='Roll Numbers and Names')

                        file_paths.append(file_path)

                        # Append data to all_data for consolidated Excel
                        roll_numbers_and_names_df['Date'] = date
                        roll_numbers_and_names_df['Session'] = session
                        roll_numbers_and_names_df['Course'] = course
                        roll_numbers_and_names_df['Room'] = room
                        all_data.append(roll_numbers_and_names_df)

                        # Add to combined_data for combined excel
                        combined_data.append((file_name, final_df))

            # Create consolidated Excel file
            consolidated_file_path = os.path.join(OUTPUT_DIR, "consolidated.xlsx")
            all_data_df = pd.concat(all_data, ignore_index=True)

            # Group data for consolidated output
            consolidated_data = []
            for (date, day, course, room), group in all_data_df.groupby(['Date', 'Session', 'Course', 'Room']):
                roll_list = ";".join(group['Roll No.'].astype(str).tolist())
                consolidated_data.append({
                    'Date': date,
                    'Day': day,
                    'course_code': course,
                    'Room': room,
                    'Allocated_students_count': len(group),
                    'Roll_list (semicolon separated_)': roll_list
                })

            # Create a DataFrame for consolidated data
            consolidated_df = pd.DataFrame(consolidated_data)

            # Display consolidated data table
            st.write("📊 **Consolidated Attendance Sheet**")
            st.dataframe(consolidated_df)

            # Save consolidated file
            consolidated_df.to_excel(consolidated_file_path, index=False, sheet_name='Consolidated Data')

            # Provide a download link for the consolidated Excel file
            st.download_button(
                label="Download Consolidated File",
                data=download_file(consolidated_file_path),
                file_name="consolidated.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

            # Provide individual download links for each attendance sheet
            st.write("📂 **Download Individual Attendance Sheets**")
            num_columns = 3
            cols = st.columns(num_columns)
            for i, file_path in enumerate(file_paths):
              col = cols[i % num_columns]  # Use modulo to cycle through columns
              with col:
                st.download_button(
                    label=f"Download {os.path.basename(file_path)}",
                    data=download_file(file_path),
                    file_name=os.path.basename(file_path),
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

            st.success("Seating arrangements generated successfully!")

        else:
            st.error("Please upload all necessary files before proceeding.")

# Run the Streamlit app
if __name__ == "__main__":
    app()
