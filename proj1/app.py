from flask import Flask, render_template, request, send_file
import pandas as pd
import os

app = Flask(__name__)

# Define a base directory for saving outputs
OUTPUT_DIR = "output"

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/submit', methods=['POST'])
def submit():
    # Get user inputs
    buffer = int(request.form['buffer'])
    sparse_option = request.form['seating']
    sparse = sparse_option == 'sparse'

    # Read uploaded files
    students_file = request.files['students_file']
    schedule_file = request.files['schedule_file']
    rooms_file = request.files['rooms_file']
    student_names_file = request.files['student_names_file']  # New file with roll number and names

    # Load data into dataframes
    students_df = pd.read_csv(students_file, skiprows=1)
    schedule_df = pd.read_csv(schedule_file, skiprows=1)
    rooms_df = pd.read_csv(rooms_file)
    student_names_df = pd.read_csv(student_names_file)  # New student names file

    # Merge student names with the roll numbers
    students_df = pd.merge(students_df, student_names_df[['Roll', 'Name']], left_on='rollno', right_on='Roll', how='left')

    # Parse morning and evening courses
    schedule_df['Morning Courses'] = schedule_df['Morning'].apply(lambda x: x.split('; ') if pd.notna(x) else [])
    schedule_df['Evening Courses'] = schedule_df['Evening'].apply(lambda x: x.split('; ') if pd.notna(x) else [])

    # Logic for seating arrangement
    def assign_rooms(courses, rooms_df, buffer, sparse):
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
                print(f"Warning: Not enough rooms for course {course} with {num_students} students remaining.")

        return assignments

    file_paths = []
    all_data = []

    for _, row in schedule_df.iterrows():
        date = row['Date']
        day = row['Day']

        for session, courses in [('Morning', row['Morning Courses']), ('Evening', row['Evening Courses'])]:
            assignments = assign_rooms(courses, rooms_df, buffer, sparse)

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

    # Create consolidated Excel file
    consolidated_file_path = os.path.join(OUTPUT_DIR, "consolidated.xlsx")
    all_data_df = pd.concat(all_data, ignore_index=True)
    all_data_df.to_excel(consolidated_file_path, index=False, sheet_name='All Data')

    # Render output page with the list of generated files
    return render_template('output.html', files=file_paths + [consolidated_file_path])


@app.route('/download/<path:filename>', methods=['GET'])
def download(filename):
    # Send the requested file to the user
    return send_file(filename, as_attachment=True)


if __name__ == '__main__':
    app.run(debug=True)
