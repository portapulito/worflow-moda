import os
from google.cloud.sql.connector import Connector
import sqlalchemy
from dotenv import load_dotenv

# Carica le variabili dal file .env
load_dotenv()

def test_cloud_sql_connection():
    """Test di connessione a Cloud SQL PostgreSQL"""
    
    print("🔌 Testando connessione Cloud SQL...")
    
    try:
        # Configurazione dalla .env
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        region = os.getenv("GOOGLE_CLOUD_LOCATION") 
        instance_name = "photo"  # Il nome della tua istanza
        database_name = os.getenv("CLOUD_SQL_DATABASE_NAME", "postgres")
        
        connection_name = f"{project_id}:{region}:{instance_name}"
        print(f"📍 Connessione a: {connection_name}")
        
        # Inizializza il connector
        connector = Connector()
        
        def getconn():
            conn = connector.connect(
                connection_name,
                "pg8000",  # Driver PostgreSQL
                user=os.getenv("CLOUD_SQL_USER"),
                password=os.getenv("CLOUD_SQL_PASSWORD"),
                db=database_name,
            )
            return conn
        
        # Crea engine SQLAlchemy
        engine = sqlalchemy.create_engine(
            "postgresql+pg8000://",
            creator=getconn,
        )
        
        # Test della connessione
        with engine.connect() as connection:
            result = connection.execute(sqlalchemy.text("SELECT 1 as test, current_timestamp as now"))
            row = result.fetchone()
            
        print("✅ Connessione riuscita!")
        print(f"📊 Test query result: {dict(row._mapping)}")
        return True
        
    except Exception as e:
        print(f"❌ Errore connessione: {e}")
        return False
    finally:
        if 'connector' in locals():
            connector.close()

if __name__ == "__main__":
    test_cloud_sql_connection()