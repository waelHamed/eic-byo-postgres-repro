#!/usr/bin/env python3
'''
PostgreSQL Database Module

This module handles connections to PostgreSQL database and provides
utility functions for executing queries.
'''
import os
import psycopg2
from psycopg2.extras import DictCursor
from mtls_logging import MtlsLogging, Severity

class Database:
    """PostgreSQL database connection handler"""
    
    def __init__(self):
        """Initialize database connection"""
        self.logger = MtlsLogging()
        self.connection = None
        self.connect()
        
    def connect(self):
        """Connect to PostgreSQL database using environment variables"""
        try:
            self.connection = psycopg2.connect(
                host=os.environ.get('POSTGRES_HOST', 'localhost'),
                port=os.environ.get('POSTGRES_PORT', '5432'),
                database=os.environ.get('POSTGRES_DB', 'helloworlddb'),
                user=os.environ.get('POSTGRES_USER', 'helloworld'),
                password=os.environ.get('POSTGRES_PASSWORD', 'helloworld')
            )
            
            # Create visits table if it doesn't exist
            self._create_tables()
            self.logger.log("Connected to PostgreSQL database", Severity.INFO)
            return True
        except Exception as e:
            self.logger.log(f"Database connection error: {str(e)}", Severity.ERROR)
            return False
            
    def _create_tables(self):
        """Create necessary tables if they don't exist"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS visits (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    endpoint VARCHAR(255) NOT NULL,
                    user_agent VARCHAR(255)
                )
            """)
            self.connection.commit()
            cursor.close()
        except Exception as e:
            self.logger.log(f"Error creating tables: {str(e)}", Severity.ERROR)
            
    def log_visit(self, endpoint, user_agent=None):
        """Log a visit to the specified endpoint"""
        if not self.connection:
            if not self.connect():
                return False
        
        try:
            cursor = self.connection.cursor()
            cursor.execute(
                "INSERT INTO visits (endpoint, user_agent) VALUES (%s, %s)",
                (endpoint, user_agent)
            )
            self.connection.commit()
            cursor.close()
            return True
        except Exception as e:
            self.logger.log(f"Error logging visit: {str(e)}", Severity.ERROR)
            # Try to reconnect on failure
            self.connect()
            return False
            
    def get_visit_count(self, endpoint=None):
        """Get the count of visits, optionally filtered by endpoint"""
        if not self.connection:
            if not self.connect():
                return 0
                
        try:
            cursor = self.connection.cursor()
            if endpoint:
                cursor.execute("SELECT COUNT(*) FROM visits WHERE endpoint = %s", (endpoint,))
            else:
                cursor.execute("SELECT COUNT(*) FROM visits")
                
            count = cursor.fetchone()[0]
            cursor.close()
            return count
        except Exception as e:
            self.logger.log(f"Error getting visit count: {str(e)}", Severity.ERROR)
            # Try to reconnect on failure
            self.connect()
            return 0
            
    def get_recent_visits(self, limit=10):
        """Get the most recent visits"""
        if not self.connection:
            if not self.connect():
                return []
                
        try:
            cursor = self.connection.cursor(cursor_factory=DictCursor)
            cursor.execute("""
                SELECT id, timestamp, endpoint, user_agent 
                FROM visits 
                ORDER BY timestamp DESC 
                LIMIT %s
            """, (limit,))
            
            results = [dict(row) for row in cursor.fetchall()]
            cursor.close()
            return results
        except Exception as e:
            self.logger.log(f"Error getting recent visits: {str(e)}", Severity.ERROR)
            # Try to reconnect on failure
            self.connect()
            return [] 