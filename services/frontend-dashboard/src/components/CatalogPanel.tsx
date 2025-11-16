import { PackagePlus, RefreshCw } from "lucide-react";
import type { CatalogItem } from "../api/types";

type Props = {
  items: CatalogItem[];
  selectedItemId: string;
  quantity: number;
  busy: boolean;
  disabled: boolean;
  onRefresh: () => void;
  onSelectItem: (itemId: string) => void;
  onQuantityChange: (quantity: number) => void;
  onCreateOrder: () => void;
};

const formatter = new Intl.NumberFormat("ru-RU", {
  style: "currency",
  currency: "RUB",
  maximumFractionDigits: 2
});

export function CatalogPanel({
  items,
  selectedItemId,
  quantity,
  busy,
  disabled,
  onRefresh,
  onSelectItem,
  onQuantityChange,
  onCreateOrder
}: Props) {
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h2>Каталог</h2>
          <p>Цена и количество фиксируются при создании заказа.</p>
        </div>
        <button className="icon-button" type="button" onClick={onRefresh} title="Обновить каталог">
          <RefreshCw size={18} />
        </button>
      </div>
      <div className="catalog-list">
        {items.map((item) => (
          <label className="catalog-item" key={item.id}>
            <input
              type="radio"
              checked={selectedItemId === item.id}
              onChange={() => onSelectItem(item.id)}
            />
            <span>
              <strong>{item.name}</strong>
              <small>{item.description}</small>
            </span>
            <b>{formatter.format(item.price_kopecks / 100)}</b>
          </label>
        ))}
      </div>
      <div className="order-controls">
        <label>
          <span>Количество</span>
          <input
            type="number"
            min={1}
            value={quantity}
            onChange={(event) =>
              onQuantityChange(Math.max(1, Number(event.target.value)))
            }
          />
        </label>
        <button
          className="primary-button"
          type="button"
          onClick={onCreateOrder}
          disabled={disabled || busy || !selectedItemId}
        >
          <PackagePlus size={18} />
          Создать заказ
        </button>
      </div>
    </section>
  );
}
