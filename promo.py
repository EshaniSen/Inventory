import pandas as pd
import streamlit as st

def calculate_allocation(df_sorted, orders_df):
    # Convert the "Freshness" column to numeric format (e.g., 0.30) for calculations
    df_sorted['Freshness'] = df_sorted['Freshness'].str.rstrip('%').astype(float) / 100
    
    # Convert the "MFG Date" column to datetime.date
    df_sorted['MFG Date'] = pd.to_datetime(df_sorted['MFG Date']).dt.date

    # Sort the DataFrame by warehouse, promotion, and manufacturing date in ascending order
    df_sorted = df_sorted.sort_values(['WH', 'Remarks', 'MFG Date'])

    # Create a new DataFrame to store the allocation results
    allocation_df = pd.DataFrame(columns=['lotNo', 'Requested', 'Previous In hand', 'Allocated', 'Remaining In hand'])

    for _, order_row in orders_df.iterrows():
        item_no = order_row['itemNo']
        ordered_qty = order_row['Requested QTY']
        warehouse = order_row['Select WH']
        ordered_date = order_row['Ordered Date']

        # Check if the itemNo exists in the DataFrame for the given warehouse
        if item_no in df_sorted.loc[df_sorted['WH'] == warehouse, 'itemNo'].values:
            # Allocate quantities based on promotions first
            promotion_lots = df_sorted.loc[
                (df_sorted['WH'] == warehouse)
                & (df_sorted['itemNo'] == item_no)
                & (df_sorted['Remarks'] == 'Promotion')
                & (df_sorted['MFG Date'] <= ordered_date)
            ]

            # If promotion lots are available and ordered date is before 15th
            if not promotion_lots.empty and ordered_date.day <= 15:
                for _, row in promotion_lots.iterrows():
                    lot_no = row['lotNo']
                    in_hand_qty = row['IN_HAND_QTY']

                    # Calculate the allocation quantity for this lotNo (considering FIFO)
                    allocation_qty = min(ordered_qty, in_hand_qty)
                    ordered_qty -= allocation_qty

                    # Append the allocation details to the temporary DataFrame
                    allocation_df = allocation_df.append(
                        {
                            'lotNo': lot_no,
                            'Requested': ordered_qty + allocation_qty,
                            'Previous In hand': in_hand_qty,
                            'Allocated': allocation_qty,
                            'Remaining In hand': in_hand_qty - allocation_qty,
                        },
                        ignore_index=True,
                    )

                    # Update the in-hand stock and total stock in df_sorted
                    df_sorted.at[_, 'IN_HAND_QTY'] -= allocation_qty
                    df_sorted.at[_, 'Total Stock'] -= allocation_qty

                    if ordered_qty <= 0:
                        break

            # Allocate the remaining quantities based on freshness (FIFO) for ordered date after 15th
            if ordered_qty > 0:
                for _, row in df_sorted.loc[
                    (df_sorted['WH'] == warehouse)
                    & (df_sorted['itemNo'] == item_no)
                    & (df_sorted['Remarks'] != 'Promotion')
                ].iterrows():
                    lot_no = row['lotNo']
                    in_hand_qty = row['IN_HAND_QTY']

                    # Calculate the allocation quantity for this lotNo (considering FIFO)
                    allocation_qty = min(ordered_qty, in_hand_qty)
                    ordered_qty -= allocation_qty

                    # Append the allocation details to the temporary DataFrame
                    allocation_df = allocation_df.append(
                        {
                            'lotNo': lot_no,
                            'Requested': ordered_qty + allocation_qty,
                            'Previous In hand': in_hand_qty,
                            'Allocated': allocation_qty,
                            'Remaining In hand': in_hand_qty - allocation_qty,
                        },
                        ignore_index=True,
                    )

                    # Update the in-hand stock and total stock in df_sorted
                    df_sorted.at[_, 'IN_HAND_QTY'] -= allocation_qty
                    df_sorted.at[_, 'Total Stock'] -= allocation_qty

                    if ordered_qty <= 0:
                        break

    # Create the "Allocated Qty" column by subtracting the initial IN_HAND_QTY from the updated IN_HAND_QTY in df_sorted
    df_sorted['Allocated Qty'] = df_sorted['IN_HAND_QTY'].copy()

    # Convert the "Freshness" column to percentages in df_sorted
    df_sorted['Freshness'] = (df_sorted['Freshness'] * 100).round(2).astype(str) + '%'

    # Format the "MFG Date" and "Expiration Date" columns to "dd-mm-yyyy" format in df_sorted
    df_sorted['MFG Date'] = pd.to_datetime(df_sorted['MFG Date']).dt.strftime('%d-%m-%Y')
    df_sorted['Expiration Date'] = pd.to_datetime(df_sorted['Expiration Date']).dt.strftime('%d-%m-%Y')

    return df_sorted, allocation_df



# Streamlit app
def main():
    st.markdown("<h1 style='text-align: center;'>Inventory Management</h1>", unsafe_allow_html=True)

    # Upload file
    uploaded_file = st.file_uploader("Upload file")
    if uploaded_file is not None:
        df = pd.read_excel(uploaded_file)  # Read the uploaded file into a DataFrame

        # Display the DataFrame
        st.subheader("Input DataFrame")
        st.write(df)

        # Format the "Freshness" column in the DataFrame to display as percentages
        df['Freshness'] = (df['Freshness'] * 100).round(2).astype(str) + '%'

        # Format the "MFG Date" and "Expiration Date" columns to "dd-mm-yyyy" format in df
        df['MFG Date'] = pd.to_datetime(df['MFG Date']).dt.strftime('%d-%m-%Y')
        df['Expiration Date'] = pd.to_datetime(df['Expiration Date']).dt.strftime('%d-%m-%Y')

        # Select SKU and warehouse
        selected_sku = st.selectbox("Select SKU", df['SKU Description'].unique())
        selected_wh = st.selectbox("Select WH", df['WH'].unique())

        # Filter DataFrame based on selected SKU and warehouse
        filtered_df = df[(df['SKU Description'] == selected_sku) & (df['WH'] == selected_wh)]

        # Display EDA table
        st.subheader("EDA")
        st.write(filtered_df[['SKU Description', 'lotNo', 'IN_HAND_QTY', 'Total Stock', 'MFG Date', 'Expiration Date', 'Freshness', 'Remarks']].to_html(index=False), unsafe_allow_html=True)  # Remove index numbers from display

        # Orders DataFrame
        orders_df = pd.DataFrame({
            'itemNo': [filtered_df.iloc[0]['itemNo']],
            'SKU Description': [filtered_df.iloc[0]['SKU Description']],
            'Select WH': [selected_wh],  # Correct column name for the warehouse
            'Requested QTY': [st.number_input("Requested QTY", min_value=1)],
            'Ordered Date': [st.date_input("Ordered Date")]
        })

        # Display Orders DataFrame
        st.subheader("Orders")
        st.write(orders_df.to_html(index=False), unsafe_allow_html=True)  # Remove index numbers from display

        # Calculate allocation
        df_sorted, allocation_df = calculate_allocation(df, orders_df)

        # Display Allocation DataFrame
        st.subheader("Allocation")
        st.write(allocation_df[['lotNo', 'Requested', 'Previous In hand', 'Allocated', 'Remaining In hand']].to_html(index=False), unsafe_allow_html=True)  # Remove index numbers from display

        # Display the updated DataFrame with allocated quantities for the selected SKU and warehouse
        st.subheader("Updated DataFrame for Selected SKU and Warehouse")
        st.write(df_sorted[(df_sorted['SKU Description'] == selected_sku) & (df_sorted['WH'] == selected_wh)][['WH', 'itemNo', 'SKU Description', 'lotNo', 'Total Stock']].to_html(index=False), unsafe_allow_html=True)  # Remove index numbers from display

# Run the Streamlit app
if __name__ == '__main__':
    main()
