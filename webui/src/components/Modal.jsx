import { FaTimes } from 'react-icons/fa'
import './Modal.css'

function Modal({ isOpen, onClose, title, children, onConfirm, confirmText = 'Confirm', confirmClass = 'btn-primary', showCancel = true }) {
  if (!isOpen) return null

  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget) {
      onClose()
    }
  }

  return (
    <div className="modal-backdrop" onClick={handleBackdropClick}>
      <div className="modal-content">
        <div className="modal-header">
          <h3>{title}</h3>
          <button className="modal-close" onClick={onClose}>
            <FaTimes />
          </button>
        </div>
        <div className="modal-body">
          {children}
        </div>
        <div className="modal-footer">
          {showCancel && (
            <button className="btn btn-secondary" onClick={onClose}>
              Cancel
            </button>
          )}
          {onConfirm && (
            <button className={`btn ${confirmClass}`} onClick={onConfirm}>
              {confirmText}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

export default Modal
