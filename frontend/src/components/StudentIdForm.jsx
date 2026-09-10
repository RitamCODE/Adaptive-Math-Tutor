import { useState } from "react";

export default function StudentIdForm({ onStart, loading }) {
  const [studentId, setStudentId] = useState("");

  function handleSubmit(event) {
    event.preventDefault();
    if (studentId.trim()) {
      onStart(studentId.trim());
    }
  }

  return (
    <form className="student-id-form" onSubmit={handleSubmit}>
      <label htmlFor="student-id">Student name</label>
      <input
        id="student-id"
        type="text"
        value={studentId}
        onChange={(event) => setStudentId(event.target.value)}
        placeholder="e.g. Alex"
        autoFocus
      />
      <button type="submit" disabled={loading || !studentId.trim()}>
        {loading ? "Starting…" : "Start"}
      </button>
    </form>
  );
}
