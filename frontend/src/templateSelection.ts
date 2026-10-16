export type Selection = { arm: string; world: string; task: string };
type Catalog = Record<'arms' | 'worlds' | 'tasks', readonly {id: string; status: string}[]>;

/** Keep every user-selectable combination executable; never substitute hardware. */
export function changeSelection(current: Selection, key: keyof Selection, id: string, catalog: Catalog): Selection {
  const group = key === 'arm' ? catalog.arms : key === 'world' ? catalog.worlds : catalog.tasks;
  const option = group.find(o => o.id === id);
  if (!option || option.status === 'reference') return current;
  const next = {...current, [key]: id};
  if(key==='arm'&&id!=='panda'&&next.task==='cloth_fold'){next.world='manufacturing';next.task='pick_place';}
  if (key === 'world') {
    if (id === 'textile') {next.task = 'cloth_fold';next.arm='panda';}
    else if (next.task === 'cloth_fold') next.task = 'pick_place';
  } else if (key === 'task') {
    if (id === 'cloth_fold') {next.world = 'textile';next.arm='panda';}
    else if (next.world === 'textile') next.world = 'manufacturing';
  }
  return next;
}
