import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const markdownComponents = {
  table(props) {
    const { node: _node, ...tableProps } = props;
    return (
      <div className="markdown-table-scroll">
        <table {...tableProps} />
      </div>
    );
  },
};

export default function MarkdownContent({ children, className = '' }) {
  const classes = ['markdown-content', className].filter(Boolean).join(' ');

  return (
    <div className={classes}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
        {children || ''}
      </ReactMarkdown>
    </div>
  );
}
