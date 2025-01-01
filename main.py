import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import streamlit as st
from datetime import datetime
from openpyxl.workbook import Workbook


# Step 1: Set up SQLite Database
def create_db():
    conn = sqlite3.connect('finance_tracker.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (
                 id INTEGER PRIMARY KEY,
                 date TEXT,
                 amount REAL,
                 category TEXT,
                 type TEXT,
                 description TEXT)''')
    conn.commit()
    conn.close()


# Step 2: Add a Transaction (Income or Expense)
def add_transaction(date, amount, category, type_, description=''):
    conn = sqlite3.connect('finance_tracker.db')
    c = conn.cursor()

    # Check for duplicates based on category, date, and description
    c.execute('''SELECT * FROM transactions WHERE date = ? AND category = ? AND type = ? AND description = ?''',
              (date.strftime("%Y-%m-%d"), category, type_, description))
    existing_transaction = c.fetchone()

    if existing_transaction:
        st.warning("This transaction already exists for the same category, date, and description. Please check before "
                   "adding.")
    else:
        c.execute('''INSERT INTO transactions (date, amount, category, type, description)
                     VALUES (?, ?, ?, ?, ?)''', (date.strftime("%Y-%m-%d"), amount, category, type_, description))
        conn.commit()
        st.success(f"Transaction for {category} added successfully!")

    conn.close()


# Step 3: Fetch Transactions for Reports
def get_transactions():
    conn = sqlite3.connect('finance_tracker.db')
    df = pd.read_sql_query("SELECT * FROM transactions", conn)
    conn.close()
    return df


# Step 4: Generate Monthly Report (Income, Expenses, and Amount Saved)
def generate_monthly_report(month, year):
    df = get_transactions()
    df['date'] = pd.to_datetime(df['date'])
    df['month'] = df['date'].dt.month
    df['year'] = df['date'].dt.year

    # Filter transactions for the selected month and year
    monthly_data = df[(df['month'] == month) & (df['year'] == year)]

    # Calculate Total Income and Total Expenses
    total_income = monthly_data[monthly_data['type'] == 'Income']['amount'].sum()
    total_expenses = monthly_data[monthly_data['type'] == 'Expense']['amount'].sum()
    saved_amount = total_income - total_expenses  # Amount saved = Income - Expenses

    # Group by Category, Type, and Description
    summary = monthly_data.groupby(['category', 'type', 'description']).agg({'amount': 'sum'}).reset_index()

    # Define custom category order to ensure 'Salary' stays on top
    category_order = ['Salary', 'Rent', 'Utilities', 'Grocery', 'Other']  # Adjust the order as needed
    summary['category_order'] = summary['category'].apply(
        lambda x: category_order.index(x) if x in category_order else len(category_order))

    # Sort the data based on the custom category order
    summary = summary.sort_values(by=['category_order', 'category', 'type', 'description'],
                                  ascending=[True, True, True, True])

    # Drop the temporary 'category_order' column
    summary = summary.drop(columns=['category_order'])

    # Add Total Income, Total Expenses, and Amount Saved to the report
    summary = pd.concat([summary, pd.DataFrame({
        'category': ['Total Income', 'Total Expenses', 'Amount Saved'],
        'type': ['', '', ''],
        'description': ['', '', ''],
        'amount': [total_income, total_expenses, saved_amount]
    })], ignore_index=True)

    return summary, total_income, total_expenses, saved_amount


# Step 5: Edit or Delete Transaction
def edit_or_delete_transaction(transaction_id, new_amount=None, new_description=None, delete=False):
    conn = sqlite3.connect('finance_tracker.db')
    c = conn.cursor()

    if delete:
        c.execute('''DELETE FROM transactions WHERE id = ?''', (transaction_id,))
        conn.commit()
        st.success(f"Transaction with ID {transaction_id} deleted successfully!")
    else:
        if new_amount is not None and new_description is not None:
            c.execute('''UPDATE transactions SET amount = ?, description = ? WHERE id = ?''',
                      (new_amount, new_description, transaction_id))
            conn.commit()
            st.success(f"Transaction with ID {transaction_id} updated successfully!")

    conn.close()


# Step 6: Data Visualization (Pie chart with Expenses Breakdown by Category)
def visualize_transactions():
    df = get_transactions()
    df['date'] = pd.to_datetime(df['date'])
    df['month'] = df['date'].dt.month
    df['year'] = df['date'].dt.year

    # Aggregate Expenses (grouped by category) and Amount Saved (Income - Expenses)
    total_income = df[df['type'] == 'Income']['amount'].sum()
    total_expenses = df[df['type'] == 'Expense']['amount'].sum()
    saved_amount = total_income - total_expenses  # Amount saved = Income - Expenses

    # Group the expenses by category
    expenses_by_category = df[df['type'] == 'Expense'].groupby('category')['amount'].sum()

    # Data for the pie chart: Expenses by Category and Amount Saved
    labels = list(expenses_by_category.index)
    amounts = list(expenses_by_category) + [saved_amount]

    # Plot the pie chart
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.pie(amounts, labels=labels + ['Amount Saved'], autopct='%1.1f%%', startangle=90,
           colors=sns.color_palette("Set2", len(amounts)))
    ax.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.
    st.pyplot(fig)


# Step 7: Reset Database
def reset_database():
    conn = sqlite3.connect('finance_tracker.db')
    c = conn.cursor()
    c.execute("DELETE FROM transactions")  # Delete all records from the transactions table
    conn.commit()
    conn.close()


def export_to_excel():
    df = get_transactions()
    df['date'] = pd.to_datetime(df['date'])

    # Create an Excel writer
    with pd.ExcelWriter('transactions_by_month.xlsx') as writer:
        # Loop over all unique months and years in the data
        for month_year, group in df.groupby([df['date'].dt.year, df['date'].dt.month]):
            year, month = month_year

            # Filter data for the selected month and year
            monthly_data = group
            total_income = monthly_data[monthly_data['type'] == 'Income']['amount'].sum()
            total_expenses = monthly_data[monthly_data['type'] == 'Expense']['amount'].sum()
            saved_amount = total_income - total_expenses

            # Add totals as new rows
            totals = pd.DataFrame({
                'date': ['Total Income', 'Total Expenses', 'Amount Saved'],
                'amount': [total_income, total_expenses, saved_amount],
                'category': ['', '', ''],
                'type': ['', '', ''],
                'description': ['', '', ''],
                'month': [month] * 3,
                'year': [year] * 3
            })

            # Combine the monthly data and totals
            full_data = pd.concat([monthly_data, totals], ignore_index=True)

            # Write the data to a sheet named by the month and year
            sheet_name = f"{year}-{month:02d}"
            full_data.to_excel(writer, index=False, sheet_name=sheet_name)

    # Provide download button for the Excel file
    st.download_button("Download Excel with Multiple Sheets", data=open('transactions_by_month.xlsx', 'rb').read(),
                       file_name='transactions_by_month.xlsx',
                       mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


# Streamlit UI for the Finance Tracker
def app():
    st.title("Finance Tracker")

    # Create DB if it doesn't exist
    create_db()

    # Input form for adding transactions
    with st.form("add_transaction_form"):
        st.header("Add Transaction")
        date = st.date_input("Date")
        amount = st.number_input("Amount", format="%.2f")
        category = st.selectbox("Category", ["Salary", "Rent", "Grocery", "Utilities", "Other"])
        transaction_type = st.radio("Transaction Type", ["Income", "Expense"])
        description = st.text_input("Description")

        submit_button = st.form_submit_button("Add Transaction")
        if submit_button:
            # Add transaction to the database
            add_transaction(date, amount, category, transaction_type, description)

    # Display Monthly Report
    st.header("Generate Monthly Report")
    month = st.number_input("Enter Month", min_value=1, max_value=12, value=1)
    year = st.number_input("Enter Year", min_value=2020, value=2024)

    if st.button("Generate Report"):
        monthly_report, total_income, total_expenses, saved_amount = generate_monthly_report(month, year)
        if monthly_report.empty:
            st.warning(f"No transactions found for {month}/{year}.")
        else:
            # Display the report in a table format
            st.dataframe(monthly_report)
            st.markdown(f"**Total Income**: ${total_income:.2f}", unsafe_allow_html=True)
            st.markdown(f"**Total Expenses**: ${total_expenses:.2f}", unsafe_allow_html=True)
            st.markdown(f"**<span style='color:green; font-weight: bold;'>Amount Saved</span>: ${saved_amount:.2f}",
                        unsafe_allow_html=True)

    # Show Data Visualization (Pie chart for Expenses Breakdown by Category and Savings)
    if st.button("Show Monthly Visualization"):
        visualize_transactions()

    # Edit or Delete Transaction Interface
    st.header("Manage Transactions")
    df = get_transactions()
    transaction_ids = df['id'].tolist()
    selected_transaction_id = st.selectbox("Select Transaction to Edit/Delete", transaction_ids)

    if selected_transaction_id:
        # Fetch selected transaction details
        selected_transaction = df[df['id'] == selected_transaction_id].iloc[0]

        # Display only relevant fields (Date, Amount, Category, Description)
        st.write(f"**Date**: {selected_transaction['date']}")
        st.write(f"**Amount**: ${selected_transaction['amount']:.2f}")
        st.write(f"**Category**: {selected_transaction['category']}")
        st.write(f"**Description**: {selected_transaction['description']}")

        # Option to edit or delete
        action = st.radio("Choose Action", ["Edit", "Delete"])

        if action == "Edit":
            new_amount = st.number_input("New Amount", value=selected_transaction['amount'], format="%.2f")
            new_description = st.text_input("New Description", value=selected_transaction['description'])
            if st.button("Update Transaction"):
                edit_or_delete_transaction(selected_transaction_id, new_amount, new_description)

        elif action == "Delete":
            if st.button("Delete Transaction"):
                edit_or_delete_transaction(selected_transaction_id, delete=True)

    # Export data to CSV
    export_to_excel()

    # Reset Database Button
    if st.button("Reset Database"):
        reset_database()
        st.success("Database has been reset!")


# Run the Streamlit app
if __name__ == '__main__':
    app()
