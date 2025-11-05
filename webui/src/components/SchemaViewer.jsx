import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  FaDatabase, 
  FaTable, 
  FaKey, 
  FaLink, 
  FaChevronDown, 
  FaChevronRight,
  FaInfoCircle,
  FaSpinner
} from 'react-icons/fa';
import './SchemaViewer.css';

const SchemaViewer = ({ databaseId, apiConfig }) => {
  const [schema, setSchema] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expandedTables, setExpandedTables] = useState({});
  const [view, setView] = useState('tables'); // 'tables' or 'relationships'

  useEffect(() => {
    if (databaseId) {
      fetchSchema();
    }
  }, [databaseId]);

  const fetchSchema = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await axios.get(
        `${apiConfig.baseUrl}/api/v1/databases/${databaseId}/schema`
      );
      setSchema(response.data);
      
      // Expand all tables by default
      const expanded = {};
      response.data.tables.forEach(table => {
        expanded[table.name] = true;
      });
      setExpandedTables(expanded);
      
    } catch (err) {
      console.error('Error fetching schema:', err);
      setError(err.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
    }
  };

  const toggleTable = (tableName) => {
    setExpandedTables(prev => ({
      ...prev,
      [tableName]: !prev[tableName]
    }));
  };

  const toggleAllTables = () => {
    const allExpanded = Object.values(expandedTables).every(v => v);
    const newState = {};
    schema.tables.forEach(table => {
      newState[table.name] = !allExpanded;
    });
    setExpandedTables(newState);
  };

  if (loading) {
    return (
      <div className="schema-viewer">
        <div className="loading-state">
          <FaSpinner className="spinner" />
          <p>Loading schema...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="schema-viewer">
        <div className="error-state">
          <p>❌ Error loading schema: {error}</p>
        </div>
      </div>
    );
  }

  if (!schema) {
    return (
      <div className="schema-viewer">
        <div className="empty-state">
          <FaDatabase size={48} />
          <p>Select a database to view its schema</p>
        </div>
      </div>
    );
  }

  return (
    <div className="schema-viewer">
      <div className="schema-header">
        <div className="header-left">
          <FaDatabase className="database-icon" />
          <div className="database-info">
            <h2>{schema.database_name}</h2>
            <p className="schema-stats">
              {schema.tables.length} tables · {schema.relationships.length} relationships
            </p>
          </div>
        </div>
        
        <div className="view-toggle">
          <button 
            className={`toggle-btn ${view === 'tables' ? 'active' : ''}`}
            onClick={() => setView('tables')}
          >
            <FaTable /> Tables
          </button>
          <button 
            className={`toggle-btn ${view === 'relationships' ? 'active' : ''}`}
            onClick={() => setView('relationships')}
          >
            <FaLink /> Relationships
          </button>
        </div>
      </div>

      {view === 'tables' ? (
        <div className="tables-view">
          <div className="tables-toolbar">
            <button className="btn-expand-all" onClick={toggleAllTables}>
              {Object.values(expandedTables).every(v => v) ? 'Collapse All' : 'Expand All'}
            </button>
          </div>

          <div className="tables-list">
            {schema.tables.map(table => (
              <div key={table.name} className="table-card">
                <div className="table-header" onClick={() => toggleTable(table.name)}>
                  <div className="table-name-section">
                    {expandedTables[table.name] ? 
                      <FaChevronDown className="expand-icon" /> : 
                      <FaChevronRight className="expand-icon" />
                    }
                    <FaTable className="table-icon" />
                    <h3>{table.name}</h3>
                    <span className="column-count">{table.columns.length} columns</span>
                  </div>
                  {table.primary_key && table.primary_key.length > 0 && (
                    <div className="pk-badge">
                      <FaKey /> PK: {table.primary_key.join(', ')}
                    </div>
                  )}
                </div>

                {table.description && (
                  <div className="table-description">
                    <FaInfoCircle className="info-icon" />
                    <span>{table.description}</span>
                  </div>
                )}

                {expandedTables[table.name] && (
                  <div className="columns-list">
                    <table className="columns-table">
                      <thead>
                        <tr>
                          <th>Column</th>
                          <th>Type</th>
                          <th>Description</th>
                        </tr>
                      </thead>
                      <tbody>
                        {table.columns.map(column => (
                          <tr key={column.name}>
                            <td className="column-name">
                              {table.primary_key?.includes(column.name) && (
                                <FaKey className="pk-icon" title="Primary Key" />
                              )}
                              <span>{column.name}</span>
                            </td>
                            <td className="column-type">{column.type}</td>
                            <td className="column-description">
                              {column.description || <em className="no-description">No description</em>}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="relationships-view">
          {schema.relationships.length === 0 ? (
            <div className="empty-state">
              <FaLink size={48} />
              <p>No foreign key relationships found</p>
            </div>
          ) : (
            <div className="relationships-list">
              {schema.relationships.map((rel, idx) => (
                <div key={idx} className="relationship-card">
                  <div className="relationship-flow">
                    <div className="rel-table">
                      <FaTable />
                      <span className="table-name">{rel.from_table}</span>
                      <span className="column-name">{rel.from_column}</span>
                    </div>
                    
                    <div className="rel-arrow">
                      <FaLink />
                    </div>
                    
                    <div className="rel-table">
                      <FaTable />
                      <span className="table-name">{rel.to_table}</span>
                      <span className="column-name">{rel.to_column}</span>
                    </div>
                  </div>
                  
                  <div className="constraint-name">
                    Constraint: <code>{rel.constraint_name}</code>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default SchemaViewer;
