import { Component, inject } from '@angular/core';
import { ActivatedRoute, RouterModule } from '@angular/router';
import { AuthFlow } from '../../auth/auth-flow';

@Component({
  selector: 'app-login',
  imports: [RouterModule],
  templateUrl: './login.html',
  styleUrl: './login.css',
})
export class Login {
  private readonly authFlow = inject(AuthFlow);
  readonly authError = inject(ActivatedRoute).snapshot.queryParamMap.get('authError');

  login(): void {
    this.authFlow.login();
  }
}
