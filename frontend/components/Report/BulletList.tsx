interface Props {

    items: string[];

}

export default function BulletList({

    items

}: Props) {

    return (

        <ul className="space-y-3">

            {items.map((item, index) => (

                <li

                    key={index}

                    className="flex gap-3"

                >

                    <span className="text-cyan-400">

                        •

                    </span>

                    <span>

                        {item}

                    </span>

                </li>

            ))}

        </ul>

    );

}