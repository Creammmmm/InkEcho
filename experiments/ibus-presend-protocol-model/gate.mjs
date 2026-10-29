// Isolated protocol model. No real D-Bus, GNOME or IBus is involved.
export class Gate {
  constructor(resolve, consume) { this.resolve=resolve; this.consume=consume; this.session=null; }
  begin(sender, token) {
    if (this.session || !this.consume(token)) return false;
    this.session={sender,next:0,attempts:0,failed:false}; return true;
  }
  commit(sender, sequence, text) {
    const s=this.session;
    if (!s || s.sender!==sender || s.failed || sequence!==s.next ||
        !Number.isSafeInteger(sequence) || typeof text!=='string' || [...text].length!==1)
      return {state:'rejected'};
    let dispatch;
    try { dispatch=this.resolve(); } catch { dispatch=null; }
    if (typeof dispatch!=='function') {
      s.failed=true;
      return {state:'no_service', prior_attempts:s.attempts};
    }
    s.next++; s.attempts++;
    try { dispatch(text); return {state:'attempted'}; }
    catch { s.failed=true; return {state:'unknown'}; }
  }
  cancel(sender) { if (!this.session || this.session.sender!==sender) return false; this.session=null; return true; }
}
export function route(reply, priorAttempts) {
  if (!reply || reply.state!=='no_service' || priorAttempts!==0 || reply.prior_attempts!==0) return 'stop';
  return 'fallback';
}
