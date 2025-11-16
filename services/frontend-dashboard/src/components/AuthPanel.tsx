import { LogIn, LogOut, UserPlus } from "lucide-react";
import { FormEvent, useState } from "react";
import { api } from "../api/client";
import type { AuthUser } from "../api/types";

type Props = {
  token: string | null;
  user: AuthUser | null;
  onLogin: (token: string, user: AuthUser) => void;
  onLogout: () => void;
};

export function AuthPanel({ token, user, onLogin, onLogout }: Props) {
  const [registerForm, setRegisterForm] = useState({
    username: "",
    email: "",
    display_name: "",
    password: ""
  });
  const [loginForm, setLoginForm] = useState({
    username: "local-user",
    password: "local-password"
  });
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  async function submitRegister(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    try {
      await api.register(registerForm);
      setMessage("Аккаунт создан. Теперь можно войти.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Регистрация не удалась");
    } finally {
      setBusy(false);
    }
  }

  async function submitLogin(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    try {
      const login = await api.login(loginForm);
      onLogin(login.access_token, login);
      setMessage("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Вход не удался");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel auth-panel">
      <div className="panel-header">
        <div>
          <h2>Аккаунт</h2>
          {user && <p>Вы вошли как {user.display_name || user.username}</p>}
        </div>
        {token && (
          <button className="icon-button" type="button" onClick={onLogout} title="Выйти">
            <LogOut size={18} />
          </button>
        )}
      </div>

      {!token && (
        <div className="auth-grid">
          <form onSubmit={submitLogin} className="form">
            <h3>Войти</h3>
            <label>
              <span>Username</span>
              <input
                value={loginForm.username}
                onChange={(event) =>
                  setLoginForm({ ...loginForm, username: event.target.value })
                }
                autoComplete="username"
              />
            </label>
            <label>
              <span>Пароль</span>
              <input
                type="password"
                value={loginForm.password}
                onChange={(event) =>
                  setLoginForm({ ...loginForm, password: event.target.value })
                }
                autoComplete="current-password"
              />
            </label>
            <button className="primary-button" disabled={busy} type="submit">
              <LogIn size={18} />
              Войти
            </button>
          </form>

          <form onSubmit={submitRegister} className="form">
            <h3>Создать аккаунт</h3>
            <label>
              <span>Username</span>
              <input
                value={registerForm.username}
                onChange={(event) =>
                  setRegisterForm({ ...registerForm, username: event.target.value })
                }
                autoComplete="username"
              />
            </label>
            <label>
              <span>Email</span>
              <input
                type="email"
                value={registerForm.email}
                onChange={(event) =>
                  setRegisterForm({ ...registerForm, email: event.target.value })
                }
                autoComplete="email"
              />
            </label>
            <label>
              <span>Имя</span>
              <input
                value={registerForm.display_name}
                onChange={(event) =>
                  setRegisterForm({
                    ...registerForm,
                    display_name: event.target.value
                  })
                }
                autoComplete="name"
              />
            </label>
            <label>
              <span>Пароль</span>
              <input
                type="password"
                value={registerForm.password}
                onChange={(event) =>
                  setRegisterForm({ ...registerForm, password: event.target.value })
                }
                autoComplete="new-password"
              />
            </label>
            <button className="secondary-button" disabled={busy} type="submit">
              <UserPlus size={18} />
              Создать аккаунт
            </button>
          </form>
        </div>
      )}

      {message && <p className="status-note">{message}</p>}
    </section>
  );
}
