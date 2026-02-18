import streamlit as st
import pandas as pd
import re
import numpy as np
from io import BytesIO
import datetime

st.set_page_config(page_title="Procesador de Reportes Zettle", layout="wide")
st.title("Procesador de archivos Excel de Zettle")
st.markdown("Sube el archivo **Zettle-Receipts-Report-... .xlsx** para generar el resumen de ventas y productos no mapeados.")

uploaded_file = st.file_uploader("Selecciona el archivo Excel", type=["xlsx", "xls"])

if uploaded_file is not None:
    try:
        # Leer el archivo con header=16 (como en tu notebook)
        df = pd.read_excel(uploaded_file, header=16)
        st.success("Archivo cargado correctamente.")
        
        # Mostrar columnas (opcional)
        with st.expander("Ver columnas del archivo original"):
            st.write("Columnas:", df.columns.tolist())
        
        # --- Procesamiento (copiado de tu nuevo código) ---
        # Seleccionar columnas de interés
        s = ['Fecha', 'Total', 'Método de pago', 'Tipo de evento', 'Descripción']
        missing = [col for col in s if col not in df.columns]
        if missing:
            st.error(f"El archivo no contiene las columnas necesarias: {missing}. Asegúrate de subir el reporte correcto.")
            st.stop()
        
        excel = df[s].copy()
        
        # Dividir Descripción en varias columnas por comas
        split_description = excel['Descripción'].str.split(',', expand=True)
        n = [f'Descripción_{i+1}' for i in range(split_description.shape[1])]
        split_description.columns = n
        excel = pd.concat([excel, split_description], axis=1)
        excel = excel.drop(columns=['Descripción'])
        
        # Reemplazar métodos de pago
        excel['Método de pago'] = excel['Método de pago'].replace(['Sin contacto', 'Chip'], 'Tarjeta')
        
        # Columnas de descripción
        description_cols = [col for col in excel.columns if col.startswith('Descripción_')]
        
        # Reemplazar patrones "cantidad x producto" por "cantidad * producto"
        pattern_to_replace_x = r'(\d+(?:\.\d+)?)\s*x\s*(.+)'
        replacement_with_star = r'\1 * \2'
        for col in description_cols:
            excel[col] = excel[col].astype(str).str.strip().replace(pattern_to_replace_x, replacement_with_star, regex=True)
        
        for col in description_cols:
            excel[col] = excel[col].fillna('')
        
        # Lista de productos a resumir y mapa de precios
        products_to_summarize = [
            'Renta de Cancha', 'Renta pala', 'Gatorade 600 ml', 'Electrolit',
            'Agua 1 lt', 'Pelotas NOX Pro Titanium', 'Agua Mineral', 'Snickers',
            'Coca-Cola 355 ml', 'Overgrip NOX'
        ]
        
        description_to_number_map = {
            'Renta de Cancha': 650, 'Renta pala': 100, 'Gatorade 600 ml': 40,
            'Electrolit': 45, 'Agua 1 lt': 30, 'Pelotas NOX Pro Titanium': 250,
            'Agua Mineral': 30, 'Snickers': 30, 'Coca-Cola 355 ml': 40,
            'Overgrip NOX': 100
        }
        
        def extract_item_details(desc_value, desc_map, products_list):
            if pd.isna(desc_value) or str(desc_value).strip() == 'None' or str(desc_value).strip() == '':
                return None, None, None
            s_val = str(desc_value).strip()
            match = re.match(r'(\d+(?:\.\d+)?)\s*\*\s*(.+)', s_val)
            if match:
                quantity = float(match.group(1))
                item_name = match.group(2).strip()
                if item_name in desc_map:
                    unit_price = desc_map[item_name]
                    return item_name, quantity, unit_price
                else:
                    return item_name, quantity, None
            if s_val in desc_map:
                quantity = 1.0
                unit_price = desc_map[s_val]
                return s_val, quantity, unit_price
            elif s_val and s_val != 'None':
                return s_val, 1.0, None
            return None, None, None
        
        reprocessed_sales_details = []
        for index, row in excel.iterrows():
            transaction_total = row['Total']
            payment_method = row['Método de pago']
            transaction_date = row['Fecha']
            current_transaction_items_raw = []
            for col in description_cols:
                description_value = row[col]
                product_name, quantity, unit_price = extract_item_details(description_value, description_to_number_map, products_to_summarize)
                if product_name is not None:
                    current_transaction_items_raw.append({
                        'Original Description': description_value,
                        'Producto': product_name,
                        'Cantidad': quantity,
                        'Precio Unitario': unit_price,
                        'Método de pago': payment_method,
                        'Fecha': transaction_date
                    })
            mapped_items = [item for item in current_transaction_items_raw if item['Precio Unitario'] is not None]
            unmapped_items = [item for item in current_transaction_items_raw if item['Precio Unitario'] is None]
            total_mapped_sales_value = sum(item['Cantidad'] * item['Precio Unitario'] for item in mapped_items)
            if len(unmapped_items) == 1:
                unmapped_item = unmapped_items[0]
                unmapped_quantity = unmapped_item['Cantidad']
                if unmapped_quantity > 0:
                    calculated_unmapped_total_sale = transaction_total - total_mapped_sales_value
                    calculated_unit_price = calculated_unmapped_total_sale / unmapped_quantity
                    unmapped_item['Precio Unitario'] = calculated_unit_price
                    unmapped_item['Total Venta'] = calculated_unmapped_total_sale
                    reprocessed_sales_details.extend(mapped_items)
                    reprocessed_sales_details.append(unmapped_item)
                else:
                    reprocessed_sales_details.extend(current_transaction_items_raw)
            elif len(unmapped_items) == 0:
                reprocessed_sales_details.extend(mapped_items)
            else:
                reprocessed_sales_details.extend(current_transaction_items_raw)
        
        sales_details_df_reprocessed = pd.DataFrame(reprocessed_sales_details)
        sales_details_df_reprocessed['Total Venta'] = sales_details_df_reprocessed['Cantidad'] * sales_details_df_reprocessed['Precio Unitario']
        
        # Productos no mapeados
        excel_unmapped_products = sales_details_df_reprocessed[~sales_details_df_reprocessed['Producto'].isin(products_to_summarize)].copy()
        excel_unmapped_products['Cantidad'] = excel_unmapped_products['Cantidad'].apply(lambda x: '' if pd.isna(x) else x)
        excel_unmapped_products['Total Venta'] = excel_unmapped_products['Total Venta'].apply(lambda x: '' if pd.isna(x) else '{:.2f}'.format(x))
        if 'Original Description' in excel_unmapped_products.columns:
            excel_unmapped_products.drop(columns=['Original Description'], inplace=True)
        if 'Fecha' in excel_unmapped_products.columns:
            excel_unmapped_products['Fecha'] = excel_unmapped_products['Fecha'].dt.strftime('%Y-%m-%d')
        
        # Crear columnas Tarjeta y Efectivo (solo para visualización, no afecta el archivo de salida)
        excel_unmapped_products['Tarjeta'] = excel_unmapped_products.apply(
            lambda row: row['Precio Unitario'] if row['Método de pago'] == 'Tarjeta' else '', axis=1
        )
        excel_unmapped_products['Efectivo'] = excel_unmapped_products.apply(
            lambda row: row['Precio Unitario'] if row['Método de pago'] == 'Efectivo' else '', axis=1
        )
        
        # Productos mapeados y resumen
        sales_details_mapped = sales_details_df_reprocessed[sales_details_df_reprocessed['Producto'].isin(products_to_summarize)].copy()
        sales_details_mapped['Total Venta'] = sales_details_mapped['Cantidad'] * sales_details_mapped['Precio Unitario']
        grouped_sales_mapped = sales_details_mapped.groupby(['Producto', 'Método de pago']).agg(
            Total_Cantidad=('Cantidad', 'sum'),
            Total_Venta=('Total Venta', 'sum')
        ).reset_index()
        pivoted_sales_mapped = grouped_sales_mapped.pivot_table(
            index='Producto',
            columns='Método de pago',
            values='Total_Venta'
        ).fillna(0)
        total_quantity_per_product_mapped = sales_details_mapped.groupby('Producto')['Cantidad'].sum().reset_index()
        total_quantity_per_product_mapped.rename(columns={'Cantidad': 'Total Cantidad Vendida'}, inplace=True)
        final_sales_summary_mapped = pd.merge(pivoted_sales_mapped, total_quantity_per_product_mapped, on='Producto', how='left')
        final_sales_summary_mapped.rename(columns={
            'Tarjeta': 'Total Venta (Tarjeta)',
            'Efectivo': 'Total Venta (Efectivo)'
        }, inplace=True)
        final_sales_summary_mapped = final_sales_summary_mapped.reset_index()
        if 'index' in final_sales_summary_mapped.columns:
            final_sales_summary_mapped = final_sales_summary_mapped.drop(columns=['index'])
        final_sales_summary_mapped.rename(columns={
            'Total Cantidad Vendida': 'Cantidad',
            'Total Venta (Tarjeta)': 'Tarjeta',
            'Total Venta (Efectivo)': 'Efectivo'
        }, inplace=True)
        # Añadir fecha de inicio
        product_min_date = sales_details_mapped.groupby('Producto')['Fecha'].min().reset_index()
        product_min_date.rename(columns={'Fecha': 'Fecha_Inicio'}, inplace=True)
        final_sales_summary_mapped = pd.merge(final_sales_summary_mapped, product_min_date, on='Producto', how='left')
        if 'Fecha_Inicio' in final_sales_summary_mapped.columns:
            final_sales_summary_mapped['Fecha_Inicio'] = final_sales_summary_mapped['Fecha_Inicio'].dt.strftime('%Y-%m-%d')
        
        # --- Mostrar resultados ---
        st.subheader("Vista previa de Productos no Mapeados (con detalle por método de pago)")
        st.dataframe(excel_unmapped_products[['Fecha', 'Producto', 'Tarjeta', 'Efectivo']].head(20))
        
        st.subheader("Resumen de Ventas (Productos Mapeados)")
        st.dataframe(final_sales_summary_mapped)
        
        # --- Preparar archivo de descarga (igual que en el notebook) ---
        # Para la hoja 'Productos no Mapeados' usamos las columnas originales: Fecha, Producto, Precio Unitario, Método de pago
        df_download_unmapped = excel_unmapped_products[['Fecha', 'Producto', 'Precio Unitario', 'Método de pago']].copy()
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_download_unmapped.to_excel(writer, sheet_name='Productos no Mapeados', index=False)
            final_sales_summary_mapped.to_excel(writer, sheet_name='Resumen de Ventas', index=False)
        
        # Generar nombre de archivo con fecha actual
        current_date = datetime.date.today().strftime('%Y%m%d')
        output_file_name = f'Cuentas_Diarias_{current_date}.xlsx'
        
        st.download_button(
            label="Descargar archivo procesado",
            data=output.getvalue(),
            file_name=output_file_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
    except Exception as e:
        st.error(f"Ocurrió un error al procesar el archivo: {e}")