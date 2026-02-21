import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import './Stage1.css';

export default function Stage1({ responses, defaultCollapsed = false }) {
  const [activeTab, setActiveTab] = useState(0);
  const [collapsed, setCollapsed] = useState(defaultCollapsed);

  if (!responses || responses.length === 0) {
    return null;
  }

  return (
    <div className="stage stage1">
      <button className="collapse-toggle" onClick={() => setCollapsed((v) => !v)}>
        {collapsed ? '▸' : '▾'} Stage 1: Individual Responses
      </button>

      {!collapsed && (
        <>
          <div className="tabs">
            {responses.map((resp, index) => (
              <button
                key={index}
                className={`tab ${activeTab === index ? 'active' : ''}`}
                onClick={() => setActiveTab(index)}
              >
                {resp.model.split('/')[1] || resp.model}
              </button>
            ))}
          </div>

          <div className="tab-content">
            <div className="model-name">{responses[activeTab].model}</div>
            <div className="response-text markdown-content">
              <ReactMarkdown>{responses[activeTab].response}</ReactMarkdown>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
