import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Phase1 from './pages/Phase1';
import Phase2 from './pages/Phase2';
import Phase3 from './pages/Phase3';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Phase1 />} />
        <Route path="/phase2" element={<Phase2 />} />
        <Route path="/phase3" element={<Phase3 />} />
      </Routes>
    </Router>
  );
}

export default App;
