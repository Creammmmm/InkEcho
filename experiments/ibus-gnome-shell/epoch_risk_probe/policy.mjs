// A dispatch-risk detector, NOT a target-receipt or lost-character detector.
export class EpochPolicy {
    constructor() { this.epoch=0;this.pending=null;this.attempts=0;this.closed=false; }
    focusChanged() { this.epoch++; }
    begin() {
        if(this.closed||this.pending) return null;
        const token={epoch:this.epoch,attempted:false,cancelled:false};
        this.pending=token;return token;
    }
    attempted(token) {
        if(token!==this.pending||this.closed||token.cancelled)return false;
        token.attempted=true;this.attempts++;return true;
    }
    cancel() {
        this.closed=true;
        if(this.pending)this.pending.cancelled=true;
    }
    finish(token) {
        if(token!==this.pending)return 'stale';
        this.pending=null;
        let result;
        if(!token.attempted)result='not_attempted';
        else if(token.cancelled)result='unknown_cancelled';
        else if(token.epoch!==this.epoch)result='unknown_focus_changed';
        else result='attempted_unconfirmed';
        if(result.startsWith('unknown'))this.closed=true;
        return result;
    }
}
